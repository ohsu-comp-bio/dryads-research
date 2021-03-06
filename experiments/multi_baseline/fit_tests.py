
import os
base_dir = os.path.dirname(__file__)

import sys
sys.path.extend([os.path.join(base_dir, '../../..')])

from HetMan.experiments.multi_baseline import *
from HetMan.features.cohorts.tcga import MutationCohort
from HetMan.experiments.mut_baseline.setup_tests import get_cohort_data
from dryadic.features.mutations import MuType

import argparse
from importlib import import_module
import pandas as pd
import dill as pickle

import time
from sklearn.metrics import roc_auc_score
from sklearn.metrics import average_precision_score as aupr_score
from operator import itemgetter


def load_output(expr_source, cohort, samp_cutoff, classif):
    out_dir = os.path.join(
        base_dir, "output", expr_source,
        "{}__samps-{}".format(cohort, samp_cutoff), classif
        )

    out_files = [(fl, int(fl.split('out__cv-')[1].split('_task-')[0]),
                  int(fl.split('_task-')[1].split('.p')[0]))
                  for fl in os.listdir(out_dir) if 'out__cv-' in fl]
    out_files = sorted(out_files, key=itemgetter(2, 1))
    
    out_df = pd.concat([
        pd.concat([
            pd.DataFrame.from_dict(pickle.load(open(os.path.join(out_dir, fl),
                                                    'rb')))
            for fl, _, task in out_files if task == task_id
            ], axis=1)
        for task_id in set([fl[2] for fl in out_files])
        ], axis=0)

    use_clf = set(out_df.Clf.values.ravel())
    if len(use_clf) != 1:
        raise ValueError("Each gene baseline testing experiment must be run "
                         "with exactly one classifier!")

    par_df = pd.concat(dict(
        out_df.Params.apply(
            lambda gn_pars: pd.DataFrame.from_records(tuple(gn_pars)), axis=1)
        ))

    return out_df.AUC, out_df.AUPR, out_df.Time, par_df, tuple(use_clf)[0]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('expr_source', type=str,
                        choices=list(expr_sources.keys()),
                        help='which TCGA expression data source to use')
    parser.add_argument('cohort', type=str, help="which TCGA cohort to use")

    parser.add_argument(
        'samp_cutoff', type=int,
        help="minimum number of mutated samples needed to test a gene"
        )

    parser.add_argument('classif', type=str,
                        help='the name of a mutation classifier')
    
    parser.add_argument(
        '--cv_id', type=int, default=6732,
        help='the random seed to use for cross-validation draws'
        )
 
    parser.add_argument(
        '--task_count', type=int, default=10,
        help='how many parallel tasks the list of types to test is split into'
        )
    parser.add_argument('--task_id', type=int, default=0,
                        help='the subset of subtypes to assign to this task')

    parser.add_argument('--verbose', '-v', action='store_true',
                        help='turns on diagnostic messages')

    # parse command-line arguments, create directory where to save results
    args = parser.parse_args()
    out_path = os.path.join(
        base_dir, 'output', args.expr_source,
        '{}__samps-{}'.format(args.cohort, args.samp_cutoff), args.classif
        )

    comb_list = pickle.load(
        open(os.path.join(base_dir, "setup",
                          "combs-list_{}__{}__samps-{}.p".format(
                              args.expr_source, args.cohort,
                              args.samp_cutoff
                            )),
             'rb')
        )

    cdata = get_cohort_data(args.expr_source, args.cohort, args.samp_cutoff,
                            cv_prop=0.75, cv_seed=2079 + 57 * args.cv_id)

    clf_info = args.classif.split('__')
    clf_module = import_module(
        'HetMan.experiments.multi_baseline.models.{}'.format(clf_info[0]))
    mut_clf = getattr(clf_module, clf_info[1].capitalize())

    out_auc = {mtype: {'train': [None] * 2, 'test': [None] * 2}
               for mtype in comb_list}
    out_aupr = {mtype: {'train': [None] * 2, 'test': [None] * 2}
                for mtype in comb_list}

    out_params = {mtype: None for mtype in comb_list}
    out_time = {mtype: None for mtype in comb_list}

    for i, mtypes in enumerate(comb_list):
        if (i % args.task_count) == args.task_id:
            clf = mut_clf()

            if args.verbose:
                print("Testing {} ...".format(' with '.join(
                    [str(mtype) for mtype in mtypes])))

            mut_genes = {mtype.subtype_list()[0][0] for mtype in mtypes}
            ex_chroms = {cdata.gene_annot[mut_gene]['chr']
                         for mut_gene in mut_genes}
            ex_genes = {gene for gene, annot in cdata.gene_annot.items()
                        if annot['chr'] in ex_chroms}

            clf.tune_coh(cdata, mtypes, exclude_genes=ex_genes,
                         tune_splits=4, test_count=36, parallel_jobs=12)
            out_params[mtypes] = {par: clf.get_params()[par]
                                  for par, _ in mut_clf.tune_priors}

            t_start = time.time()
            clf.fit_coh(cdata, mtypes, exclude_genes=ex_genes)
            t_end = time.time()
            out_time[mtypes] = t_end - t_start

            pheno_list = dict()
            train_omics, pheno_list['train'] = cdata.train_data(
                mtypes, exclude_genes=ex_genes)
            test_omics, pheno_list['test'] = cdata.test_data(
                mtypes, exclude_genes=ex_genes)

            pred_scores = {
                'train': clf.parse_preds(clf.predict_omic(train_omics)),
                'test': clf.parse_preds(clf.predict_omic(test_omics))
                }

            samp_sizes = {
                'train': [(len(mtype.get_samples(cdata.train_mut))
                           / len(cdata.train_samps)) for mtype in mtypes],
                'test': [(len(mtype.get_samples(cdata.test_mut))
                          / len(cdata.test_samps)) for mtype in mtypes]
                }

            for samp_set, scores in pred_scores.items():
                for i in range(2):
                    if len(set(pheno_list[samp_set][:, i])) == 2:

                        out_auc[mtypes][samp_set][i] = roc_auc_score(
                            pheno_list[samp_set][:, i], scores[:, i])
                        out_aupr[mtypes][samp_set][i] = aupr_score(
                            pheno_list[samp_set][:, i], scores[:, i])
 
                    else:
                        out_auc[mtypes][samp_set][i] = 0.5
                        out_aupr[mtypes][samp_set][i] = samp_sizes[samp_set]

        else:
            del(out_auc[mtypes])
            del(out_aupr[mtypes])
            del(out_params[mtypes])
            del(out_time[mtypes])

    pickle.dump(
        {'AUC': out_auc, 'AUPR': out_aupr,
         'Clf': mut_clf, 'Params': out_params, 'Time': out_time},
        open(os.path.join(out_path,
                          'out__cv-{}_task-{}.p'.format(
                              args.cv_id, args.task_id)),
             'wb')
        )


if __name__ == "__main__":
    main()

