"""
This script runs a portion of the subgrouping classification tasks for a given
experiment. This portion is determined by `task_id` (which of the subgrouping
tasks have been assigned to this parallelized job) and `cv_id` (which of the
cross-validation fold iterations have been assigned to this job).

See .Snakefile for how this script is invoked in the run_test pipeline.

Example usage:
    python -m dryads-research.experiments.subgrouping_test.fit_test \
        Ridge temp/Firehose__BRCA_LumA/Consq__Exon --task_id 2 --cv_id 5

"""

from .classifiers import *
from ..utilities.handle_input import safe_load
from ..utilities.mutations import RandomType
from ..utilities.pipeline_setup import get_task_count
from ..utilities.misc import transfer_model

import os
import argparse
import dill as pickle
import random
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        'fit_test',
        description="Runs a portion of an experiment's classification tasks."
        )

    parser.add_argument('classif', type=str,
                        help="a classifier in HetMan.predict.classifiers")
    parser.add_argument('use_dir', type=str)

    parser.add_argument('--task_id', type=int, default=0,
                        help='the subset of subtypes to assign to this job')
    parser.add_argument('--cv_id', type=int, default=0,
                        help='the subset of cv-folds to assign to this job')

    # collect command line arguments, get directory where enumeration output
    # was stored, get the number of experiment tasks from task manifest
    args = parser.parse_args()
    setup_dir = os.path.join(args.use_dir, 'setup')
    task_count = get_task_count(args.use_dir)

    # load list of mutations to test and the expression gene features to
    # use during classifier training
    with open(os.path.join(setup_dir, "muts-list.p"), 'rb') as muts_f:
        mtype_list = pickle.load(muts_f)
    with open(os.path.join(setup_dir, "feat-list.p"), 'rb') as fl:
        feat_list = pickle.load(fl)

    # load cohort expression and mutation data and the mutation classifier
    coh_path = os.path.join(setup_dir, "cohort-data.p.gz")
    cdata = safe_load(coh_path, retry_pause=41)
    clf = eval(args.classif)
    mut_clf = clf()

    # figure out which cohort samples will be used for tuning and training the
    # classifier and which samples will be used for testing
    use_seed = 9073 + 97 * args.cv_id
    cdata_samps = sorted(cdata.get_samples())
    random.seed((args.cv_id // 4) * 7712 + 13)
    random.shuffle(cdata_samps)
    cdata.update_split(use_seed, test_samps=cdata_samps[(args.cv_id % 4)::4])

    # get the gene associated with each mutation subgrouping where applicable
    mtype_genes = {mtype: tuple(mtype.label_iter())[0] for mtype in mtype_list
                   if not isinstance(mtype, RandomType)}

    # initialize objects for storing experiment output
    out_pars = {mtype: {par: None for par, _ in mut_clf.tune_priors}
                for mtype in mtype_list}
    out_time = {mtype: dict() for mtype in mtype_list}
    out_acc = {mtype: dict() for mtype in mtype_list}
    out_pred = {mtype: dict() for mtype in mtype_list}
    out_coef = {mtype: dict() for mtype in mtype_list}

    coh_dict = {coh_fl.stem.split('__')[-1]: coh_fl
                for coh_fl in Path(setup_dir).glob("cohort-data__*.p")}
    out_trnsf = {mtype: {coh: None for coh in coh_dict}
                 for mtype in mtype_list}

    random.seed(10301)
    random.shuffle(mtype_list)

    # for each subgrouping, check if it has been assigned to this task
    for i, mtype in enumerate(mtype_list):
        if (i % task_count) == args.task_id:
            print("Testing {} ...".format(mtype))

            # get the gene associated with this subgrouping...
            if not isinstance(mtype, RandomType):
                use_gene = mtype_genes[mtype]
            elif mtype.base_mtype is not None:
                use_gene = tuple(mtype.label_iter())[0]

            # picking one at random from those associated with non-random
            # subgroupings for random subgroupings not associated with a gene
            else:
                use_gene = random.choice(list(mtype_genes.values()))

            # get the expression features on the same chromosome as the gene
            # of the mutation, remove them from features used in classifying
            ex_genes = cdata.get_cis_genes('Chrm', cur_genes=[use_gene])
            use_feats = feat_list - ex_genes

            # tune the hyper-parameters of the classifier
            mut_clf, cv_output = mut_clf.tune_coh(
                cdata, mtype, include_feats=use_feats,
                tune_splits=4, test_count=mut_clf.test_count, parallel_jobs=8
                )

            # save the tuned values of the hyper-parameters
            clf_params = mut_clf.get_params()
            for par, _ in mut_clf.tune_priors:
                out_pars[mtype][par] = clf_params[par]

            out_time[mtype]['avg'] = cv_output['mean_fit_time']
            out_time[mtype]['std'] = cv_output['std_fit_time']
            out_acc[mtype]['avg'] = cv_output['mean_test_score']
            out_acc[mtype]['std'] = cv_output['std_test_score']
            out_acc[mtype]['par'] = cv_output['params']

            # train the classifier on the entire training subcohort and apply
            # the fit model to the testing subcohort
            mut_clf.fit_coh(cdata, mtype, include_feats=use_feats)
            out_coef[mtype] = mut_clf.get_coef()

            # apply the model to the testing subcohort to get predicted labels
            out_pred[mtype] = np.round(mut_clf.parse_preds(
                mut_clf.predict_test(cdata, lbl_type='raw',
                                     include_feats=use_feats)
                ), 7)

            # apply the fit model to the entirety of each other cohort
            out_trnsf[mtype] = {
                coh: np.round(mut_clf.parse_preds(
                    transfer_model(trnsf_fl, mut_clf, use_feats)), 7)
                for coh, trnsf_fl in coh_dict.items()
                }

        else:
            del(out_pars[mtype])
            del(out_time[mtype])
            del(out_acc[mtype])
            del(out_pred[mtype])
            del(out_coef[mtype])
            del(out_trnsf[mtype])

    # save experiment results to file
    with open(os.path.join(args.use_dir, 'output',
                           "out__cv-{}_task-{}.p".format(
                               args.cv_id, args.task_id)),
              'wb') as fl:
        pickle.dump({'Pred': out_pred, 'Pars': out_pars, 'Time': out_time,
                     'Acc': out_acc, 'Coef': out_coef, 'Transfer': out_trnsf,
                     'Clf': mut_clf.__class__},
                    fl, protocol=-1)


if __name__ == "__main__":
    main()

