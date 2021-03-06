
import os
base_dir = os.path.dirname(__file__)

import sys
sys.path.extend([os.path.join(base_dir, '../../..')])

from HetMan.experiments.module_partition import *
from HetMan.features.cohorts.tcga import MutationCohort
from dryadic.features.mutations import MuType

import argparse
import synapseclient
import dill as pickle

from functools import reduce
from operator import or_
from itertools import combinations as combn
from itertools import chain


def main():
    parser = argparse.ArgumentParser(
        "Set up the paired-gene subtype expression effect isolation "
        "experiment by enumerating the subtypes to be tested."
        )

    # create positional command line arguments
    parser.add_argument('cohort', type=str, help="which TCGA cohort to use")
    parser.add_argument('mut_levels', type=str,
                        help="the mutation property levels to consider")
    parser.add_argument('genes', type=str, nargs='+',
                        help="a list of mutated genes")

    # create optional command line arguments
    parser.add_argument('--samp_cutoff', type=int, default=20,
                        help='subtype sample frequency threshold')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='turns on diagnostic messages')

    # parse command line arguments, create directory where found subtypes
    # will be stored
    args = parser.parse_args()
    use_lvls = args.mut_levels.split('__')
    out_path = os.path.join(base_dir, 'setup', args.cohort,
                            '_'.join(args.genes))
    os.makedirs(out_path, exist_ok=True)

    # log into Synapse using locally stored credentials
    syn = synapseclient.Synapse()
    syn.cache.cache_root_dir = syn_root
    syn.login()
 
    cdata = MutationCohort(cohort=args.cohort, mut_genes=args.genes,
                           mut_levels=['Gene'] + use_lvls,
                           expr_source='Firehose', var_source='mc3',
                           copy_source='Firehose', annot_file=annot_file,
                           expr_dir=expr_dir, cv_prop=1.0, syn=syn)

    iso_mtypes = set()
    if args.verbose:
        print("Looking for combinations of subtypes of mutations in genes "
              "{} present in at least {} of the samples in TCGA cohort "
              "{} at annotation levels {}.\n".format(
                  ' and '.join(args.genes),
                  args.samp_cutoff, args.cohort, use_lvls)
                )

    all_mtype = MuType(cdata.train_mut.allkey())
    test_mtypes = cdata.train_mut.branchtypes(min_size=10)

    gene_mtypes = {mtype for mtype in test_mtypes
                   if mtype.get_levels() == {'Gene'}}
    pnt_mtypes = {mtype for mtype in test_mtypes
                  if (mtype.subtype_list()[0][1]
                      == MuType({('Scale', 'Point'): None}))}

    cna_mtypes = {mtype for mtype in test_mtypes
                  if 'Copy' in mtype.get_levels()}
    sub_mtypes = {mtype for mtype in test_mtypes
                  if mtype.get_levels() & set(use_lvls)}

    comb_mtypes = {
        reduce(or_, mtypes)
        for mtypes in chain.from_iterable(combn(sub_mtypes | pnt_mtypes, r)
                                          for r in range(1, 4))
        if all((mtype1 & mtype2).is_empty()
               for mtype1, mtype2 in combn(mtypes, 2))
        }

    use_mtypes = {
        mtype for mtype in comb_mtypes | cna_mtypes
        if len(mtype.get_samples(cdata.train_mut)) >= args.samp_cutoff
        }

    if args.verbose:
        print("\nFound {} potential sub-types!".format(len(use_mtypes)))

    only_mtypes = {
        (mtype, ) for mtype in use_mtypes
        if (args.samp_cutoff
            <= len(mtype.get_samples(cdata.train_mut)
                   - (all_mtype - mtype).get_samples(cdata.train_mut))
            <= (len(cdata.samples) - args.samp_cutoff))
        }

    comb_mtypes = {
        (mtype1, mtype2) for mtype1, mtype2 in combn(use_mtypes, 2)
        if ((mtype1 & mtype2).is_empty()
            and (args.samp_cutoff
                 <= len((mtype1.get_samples(cdata.train_mut)
                         & mtype2.get_samples(cdata.train_mut))
                        - (mtype1.get_samples(cdata.train_mut)
                           ^ mtype2.get_samples(cdata.train_mut))
                        - (all_mtype - mtype1 - mtype2).get_samples(
                            cdata.train_mut))
                 <= (len(cdata.samples) - args.samp_cutoff)))
        }

    if args.verbose:
        print("\nFound {} exclusive sub-types and {} combination sub-types "
              "to isolate!".format(len(only_mtypes), len(comb_mtypes)))

    # save the list of found non-duplicate sub-types to file
    pickle.dump(
        sorted(only_mtypes | comb_mtypes),
        open(os.path.join(out_path,
                          'mtypes_list__samps_{}__levels_{}.p'.format(
                              args.samp_cutoff, args.mut_levels)),
             'wb')
        )

    with open(os.path.join(out_path,
                           'mtypes_count__samps_{}__levels_{}.txt'.format(
                               args.samp_cutoff, args.mut_levels)),
              'w') as fl:

        fl.write(str(len(only_mtypes | comb_mtypes)))


if __name__ == '__main__':
    main()

