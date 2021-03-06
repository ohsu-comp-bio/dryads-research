"""
This script loads and pre-processes the input datasets that will be used for a
given run of the subgrouping testing experiment and uses the genomic data to
enumerate the subgrouping tasks to be tested.

See .run_test for how this script is invoked in the experiment pipeline.

Example usages:
    python -m dryads-research.experiments.subgrouping_test.setup_test \
        microarray METABRIC_LumA 20 Consequence__Exon temp/

    python -m dryads-research.experiments.subgrouping_test.setup_test \
        Firehose BRCA_LumA 20 Exon__HGVSp \
        /usr/bobby/temp/Firehose/BRCA_LumA__samps-20/Exon__HGVSp

    python -m dryads-research.experiments.subgrouping_test.setup_test \
        Firehose STAD 20 Pfam-domain__Consequence \
        /tmp/users/timmy/Firehose__STAD/Pfam-domain__Consequence

"""

from ..utilities.mutations import (pnt_mtype, copy_mtype,
                                   dup_mtype, loss_mtype, RandomType)
from dryadic.features.mutations import MuType

from ..utilities.data_dirs import vep_cache_dir, expr_sources
from ...features.data.oncoKB import get_gene_list
from ...features.cohorts.utils import get_cohort_data, load_cohort
from ...features.cohorts.tcga import list_cohorts

import os
import argparse
import bz2
import dill as pickle
import subprocess

import numpy as np
import random
from itertools import product


def main():
    parser = argparse.ArgumentParser(
        'setup_test',
        description="Load datasets and enumerate subgroupings to be tested."
        )

    parser.add_argument('expr_source', help="a source of expression datasets")
    parser.add_argument('cohort', help="a tumour sample -omic dataset")

    parser.add_argument(
        'samp_cutoff', type=int,
        help="minimum number of affected samples needed to test a mutation"
        )
    parser.add_argument('mut_levels', type=str,
                        help="a combination of mutation attribute levels")

    parser.add_argument('out_dir', type=str,
                        help="the working directory for this experiment")

    # parse command line arguments, figure out where output will be stored,
    # get the mutation attributes and cancer genes that will be used
    args = parser.parse_args()
    out_path = os.path.join(args.out_dir, 'setup')
    lvl_list = ('Gene', 'Scale', 'Copy') + tuple(args.mut_levels.split('__'))
    use_genes = get_gene_list(min_sources=2)

    # load and process the -omic datasets for this cohort
    cdata = get_cohort_data(args.cohort, args.expr_source, lvl_list,
                            vep_cache_dir, out_path, use_genes)
    with bz2.BZ2File(os.path.join(out_path, "cohort-data.p.gz"), 'w') as f:
        pickle.dump(cdata, f, protocol=-1)

    # get the maximum number of samples allowed per subgrouping, initialize
    # the list of enumerated subgroupings
    max_samps = len(cdata.get_samples()) - args.samp_cutoff
    use_mtypes = set()

    # for each gene with enough samples harbouring its point mutations in the
    # cohort, find the subgroupings composed of at most two branches
    for gene, mtree in cdata.mtrees[lvl_list]:
        if len(pnt_mtype.get_samples(mtree)) >= args.samp_cutoff:
            pnt_mtypes = {
                mtype for mtype in mtree['Point'].combtypes(
                    comb_sizes=(1, 2), min_type_size=args.samp_cutoff)
                if (args.samp_cutoff
                    <= len(mtype.get_samples(mtree)) <= max_samps)
                }

            # remove subgroupings that have only one child subgrouping
            # containing all of their samples
            pnt_mtypes -= {
                mtype1 for mtype1, mtype2 in product(pnt_mtypes, repeat=2)
                if mtype1 != mtype2 and mtype1.is_supertype(mtype2)
                and mtype1.get_samples(mtree) == mtype2.get_samples(mtree)
                }

            # remove groupings that contain all of the gene's point mutations
            pnt_mtypes = {MuType({('Scale', 'Point'): mtype})
                          for mtype in pnt_mtypes
                          if (len(mtype.get_samples(mtree['Point']))
                              < len(mtree['Point'].get_samples()))}

            # check if this gene had at least five samples with deep gains or
            # deletions that weren't all already carrying point mutations
            copy_mtypes = {
                mtype for mtype in [dup_mtype, loss_mtype]
                if ((5 <= len(mtype.get_samples(mtree))
                     <= (len(cdata.get_samples()) - 5))
                    and not (mtype.get_samples(mtree)
                             <= mtree['Point'].get_samples())
                    and not (mtree['Point'].get_samples()
                             <= mtype.get_samples(mtree)))
                }

            # find the enumerated point mutations for this gene that can be
            # combined with CNAs to produce a novel set of mutated samples
            dyad_mtypes = {
                pt_mtype | cp_mtype
                for pt_mtype, cp_mtype in product(pnt_mtypes, copy_mtypes)
                if ((pt_mtype.get_samples(mtree)
                     - cp_mtype.get_samples(mtree))
                    and (cp_mtype.get_samples(mtree)
                         - pt_mtype.get_samples(mtree)))
                }

            # if we are using the base list of mutation attributes, add the
            # gene-wide set of all point mutations...
            gene_mtypes = pnt_mtypes | dyad_mtypes
            if args.mut_levels == 'Consequence__Exon':
                gene_mtypes |= {pnt_mtype}

                # ...as well as CNA-only subgroupings...
                gene_mtypes |= {
                    mtype for mtype in copy_mtypes
                    if (args.samp_cutoff
                        <= len(mtype.get_samples(mtree)) <= max_samps)
                    }

                # ...and finally the CNA + all point mutations subgroupings
                gene_mtypes |= {
                    pnt_mtype | mtype for mtype in copy_mtypes
                    if (args.samp_cutoff
                        <= len((pnt_mtype | mtype).get_samples(mtree))
                        <= max_samps)
                    }

            use_mtypes |= {MuType({('Gene', gene): mtype})
                           for mtype in gene_mtypes}

    # set a random seed for use in picking random subgroupings
    lvls_seed = np.prod([(ord(char) % 7 + 3)
                         for i, char in enumerate(args.mut_levels)
                         if (i % 5) == 1])

    # makes sure random subgroupings are the same between different runs
    # of this experiment
    mtype_list = sorted(use_mtypes)
    random.seed((88701 * lvls_seed + 1313) % (2 ** 17))
    random.shuffle(mtype_list)

    # generate random subgroupings chosen from all samples in the cohort
    use_mtypes |= {
        RandomType(size_dist=len(mtype.get_samples(cdata.mtrees[lvl_list])),
                   seed=(lvls_seed * (i + 3751) + 19207) % (2 ** 26))
        for i, (mtype, _) in enumerate(product(mtype_list, range(5)))
        if (mtype & copy_mtype).is_empty()
        }

    # generate random subgroupings chosen from samples mutated for each gene
    use_mtypes |= {
        RandomType(
            size_dist=len(mtype.get_samples(cdata.mtrees[lvl_list])),
            base_mtype=MuType({
                ('Gene', tuple(mtype.label_iter())[0]): pnt_mtype}),
            seed=(lvls_seed * (i + 1021) + 7391) % (2 ** 23)
            )

        for i, (mtype, _) in enumerate(product(mtype_list, range(5)))
        if ((mtype & copy_mtype).is_empty()
            and tuple(mtype.subtype_iter())[0][1] != pnt_mtype)
        }

    # save enumerated subgroupings and number of subgroupings to file
    with open(os.path.join(out_path, "muts-list.p"), 'wb') as f:
        pickle.dump(sorted(use_mtypes), f, protocol=-1)
    with open(os.path.join(out_path, "muts-count.txt"), 'w') as fl:
        fl.write(str(len(use_mtypes)))

    # get list of available cohorts for transference of classifiers
    coh_list = list_cohorts('Firehose', expr_dir=expr_sources['Firehose'],
                            copy_dir=expr_sources['Firehose'])
    coh_list -= {args.cohort}
    coh_list |= {'METABRIC', 'beatAML', 'CCLE'}

    # initiate set of genetic expression features, reset random seed
    coh_dir = os.path.join(args.out_dir.split('subgrouping_test')[0],
                           'subgrouping_test', 'setup')
    use_feats = set(cdata.get_features())
    random.seed()

    # for each cohort used for transferring...
    for coh in random.sample(coh_list, k=len(coh_list)):
        coh_base = coh.split('_')[0]

        # ...choose a default source of expression data
        if coh_base in {'METABRIC', 'CCLE'}:
            use_src = 'microarray'
        elif coh_base in {'beatAML'}:
            use_src = 'toil__gns'
        else:
            use_src = 'Firehose'

        # ...figure out where to store its pickled representation
        coh_tag = "cohort-data__{}__{}.p".format(use_src, coh)
        coh_path = os.path.join(coh_dir, coh_tag)

        # load and process the cohort's -omic datasets, update the list of
        # expression features common across all cohorts
        trnsf_cdata = load_cohort(coh, use_src, lvl_list, vep_cache_dir,
                                  coh_path, out_path, use_genes)
        use_feats &= set(trnsf_cdata.get_features())

        with open(coh_path, 'wb') as f:
            pickle.dump(trnsf_cdata, f, protocol=-1)

        copy_prc = subprocess.run(['cp', coh_path,
                                   os.path.join(out_path, coh_tag)],
                                  check=True)

    with open(os.path.join(out_path, "feat-list.p"), 'wb') as f:
        pickle.dump(use_feats, f, protocol=-1)


if __name__ == '__main__':
    main()

