
import os
import sys

base_dir = os.path.join(os.environ['DATADIR'],
                        'HetMan', 'subvariant_transfer')
sys.path.extend([os.path.join(os.path.dirname(__file__), '../../..')])
plot_dir = os.path.join(base_dir, 'plots', 'gene')

from HetMan.experiments.subvariant_transfer import *
from HetMan.experiments.subvariant_infer import variant_clrs
from HetMan.experiments.subvariant_infer.setup_infer import Mcomb, ExMcomb

from HetMan.experiments.utilities.scatter_plotting import place_annot
from HetMan.features.data.copies import get_copies_firehose
from dryadic.features.mutations import MuType
from dryadic.features.cohorts.utils import match_tcga_samples

import argparse
import dill as pickle
from glob import glob
import numpy as np
import pandas as pd

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

plt.rcParams['axes.facecolor']='white'
plt.rcParams['savefig.facecolor']='white'
plt.rcParams['axes.linewidth'] = 1.5
plt.rcParams['axes.edgecolor'] = 'black'

loss_clrs = sns.light_palette(variant_clrs['Loss'], 5)
gain_clrs = sns.light_palette(variant_clrs['Gain'], 5)
use_marks = [(0, 3, 0)]
use_marks += [(i, 0, k) for k in (0, 140) for i in (3, 4, 5)]


def plot_auc_comparisons(auc_dict, stat_dict, type_dict, args):
    fig, axarr = plt.subplots(figsize=(10, 9), nrows=2, ncols=2)

    for mtype in auc_dict['All']['Reg']:
        if type_dict[mtype] in variant_clrs:
            mtype_clr = variant_clrs[type_dict[mtype]]
        else:
            mtype_clr = '0.5'

        for coh, tst_coh in auc_dict['All']['Reg'][mtype]:
            mtype_size = (0.71 * np.sum(stat_dict[tst_coh, mtype])) ** 0.43

            if coh == tst_coh:
                axarr[0, 0].plot(
                    auc_dict['All']['Reg'][mtype][(coh, tst_coh)],
                    auc_dict['Iso']['Reg'][mtype][(coh, tst_coh)],
                    marker='o', markersize=mtype_size,
                    color=mtype_clr, alpha=0.31)

                for coh2, tst_coh2 in auc_dict['All']['Reg'][mtype]:
                    if coh2 == coh and tst_coh2 != tst_coh:
                        axarr[0, 1].plot(
                            auc_dict['All']['Reg'][mtype][(coh, tst_coh)],
                            auc_dict['All']['Reg'][mtype][(coh, tst_coh2)],
                            marker='o', markersize=mtype_size,
                            color=mtype_clr, alpha=0.31
                            )

                        axarr[1, 0].plot(
                            auc_dict['Iso']['Reg'][mtype][(coh, tst_coh)],
                            auc_dict['Iso']['Reg'][mtype][(coh, tst_coh2)],
                            marker='o', markersize=mtype_size,
                            color=mtype_clr, alpha=0.31
                            )

            else:
                axarr[1, 1].plot(
                    auc_dict['All']['Reg'][mtype][(coh, tst_coh)],
                    auc_dict['Iso']['Reg'][mtype][(coh, tst_coh)],
                    marker='o', markersize=mtype_size,
                    color=mtype_clr, alpha=0.31
                    )

    plot_min = min(auc_val for samp_dict in auc_dict.values()
                   for mtype_dict in samp_dict['Reg'].values()
                   for auc_val in mtype_dict.values()) - 0.02

    for ax in axarr.flatten():
        ax.plot([-1, 2], [-1, 2],
                linewidth=1.5, linestyle='--', color='#550000', alpha=0.49)

        ax.axhline(y=0.5,
                   linewidth=0.9, linestyle='--', color='black', alpha=0.29)
        ax.axvline(x=0.5,
                   linewidth=0.9, linestyle='--', color='black', alpha=0.29)

        ax.grid(color='0.23', linewidth=0.7, alpha=0.21)
        ax.set_xlim(plot_min, 1.005)
        ax.set_ylim(plot_min, 1.005)
        ax.tick_params(labelsize=10, pad=2.7)

    axarr[0, 0].set_xlabel("Default AUC", fontsize=17, weight='semibold')
    axarr[0, 0].set_ylabel("Isolated AUC", fontsize=17, weight='semibold')

    axarr[0, 1].set_xlabel("Default AUC", fontsize=17, weight='semibold')
    axarr[0, 1].set_ylabel("Transfer Default AUC",
                           fontsize=17, weight='semibold')

    axarr[1, 0].set_xlabel("Isolated AUC", fontsize=17, weight='semibold')
    axarr[1, 0].set_ylabel("Transfer Isolated AUC",
                           fontsize=17, weight='semibold')

    axarr[1, 1].set_xlabel("Transfer Default AUC",
                           fontsize=17, weight='semibold')
    axarr[1, 1].set_ylabel("Transfer Isolated AUC",
                           fontsize=17, weight='semibold')

    fig.tight_layout(pad=3.7, w_pad=3.1, h_pad=2.3)
    fig.savefig(
        os.path.join(plot_dir, "{}__samps-{}".format('__'.join(args.cohorts),
                                                     args.samp_cutoff),
                     args.gene,
                     "{}_{}__acc-comparisons.svg".format(args.classif,
                                                         args.ex_mtype)),
        dpi=500, bbox_inches='tight', format='svg'
        )

    plt.close()


def plot_copy_calls(cohort, all_df, iso_df, copy_dict, copy_norml,
                    auc_dict, stat_dict, coh_stat, type_dict, args):
    use_mtypes = {mtype for coh, mtype in all_df.index
                  if (coh == cohort
                      and mtype.subtype_list()[0][0] == args.gene)}

    fig, axarr = plt.subplots(figsize=(14, 1 + 4 * len(use_mtypes)),
                              nrows=len(use_mtypes), ncols=2)

    copy_vals = copy_dict[copy_norml][args.gene]
    copy_ctfs = {
        'ShalDel': copy_vals[stat_dict['ShalDel'] & coh_stat[cohort]].max(),
        'ShalGain': copy_vals[stat_dict['ShalGain'] & coh_stat[cohort]].min(),
        }

    for i, mtype in enumerate(use_mtypes):
        mut_stat = stat_dict[cohort, mtype]
        wt_stat = ~stat_dict[cohort, mtype] & coh_stat[cohort]

        if type_dict[mtype] in variant_clrs:
            mtype_clr = variant_clrs[type_dict[mtype]]
        else:
            mtype_clr = '0.3'

        all_vals = all_df.loc[[(cohort, mtype)]].values[0]
        all_means = np.array([np.mean(vals) for vals in all_vals])
        iso_vals = iso_df.loc[[(cohort, mtype)]].values[0]
        iso_means = np.array([np.mean(vals) for vals in iso_vals])

        for j, vals in enumerate([all_means, iso_means]):
            axarr[i, j].plot(copy_vals[mut_stat], vals[mut_stat],
                             color=mtype_clr, marker='o', linewidth=0,
                             markersize=6, markeredgecolor='none', alpha=0.23)

            axarr[i, j].plot(copy_vals[wt_stat], vals[wt_stat],
                             color='0.6', marker='o', linewidth=0,
                             markersize=4, markeredgecolor='none', alpha=0.17)

            axarr[i, j].axvline(copy_ctfs['ShalDel'], color=loss_clrs[-3],
                                linewidth=4, linestyle=':', alpha=0.47)
            axarr[i, j].axvline(copy_ctfs['ShalGain'], color=gain_clrs[-3],
                                linewidth=4, linestyle=':', alpha=0.47)

            if copy_norml:
                axarr[i, j].set_xlim(max(-3, axarr[i, j].get_xlim()[0]),
                                     min(3, axarr[i, j].get_xlim()[1]))

                axarr[i, j].axvline(-1, color=loss_clrs[-1],
                                    linewidth=4, linestyle=':', alpha=0.47)
                axarr[i, j].axvline(1, color=gain_clrs[-1],
                                    linewidth=4, linestyle=':', alpha=0.47)

            axarr[i, j].set_yticks([])
            if i != (len(use_mtypes) - 1):
                axarr[i, j].set_xticks([])
            else:
                axarr[i, j].tick_params(labelsize=13, pad=3)

    axarr[0, 0].text(0.5, 1.02, "With Other {} Mutations".format(args.gene),
                     size=19, ha='center', va='bottom', fontweight='semibold',
                     transform=axarr[0, 0].transAxes)
    axarr[0, 1].text(0.5, 1.02,
                     "Without Other {} Mutations".format(args.gene),
                     size=19, ha='center', va='bottom', fontweight='semibold',
                     transform=axarr[0, 1].transAxes)

    fig.text(0.5, 0.05, "GISTIC Copy Number Score", size=23,
             ha='center', va='top', fontweight='semibold')

    if copy_norml:
        plt_lbl = "{}_{}_{}_normed-copy-calls.svg".format(
            args.classif, args.ex_mtype, cohort)
    else:
        plt_lbl = "{}_{}_{}_copy-calls.svg".format(
            args.classif, args.ex_mtype, cohort)

    fig.tight_layout(pad=3.7, w_pad=3.1, h_pad=2.3)
    fig.savefig(
        os.path.join(plot_dir, "{}__samps-{}".format('__'.join(args.cohorts),
                                                     args.samp_cutoff),
                     args.gene, plt_lbl),
        dpi=500, bbox_inches='tight', format='svg'
        )

    plt.close()


def main():
    parser = argparse.ArgumentParser(
        "Plot how isolating subvariants affects classification performance "
        "within and between cohorts for a gene in a transfer experiment."
        )

    parser.add_argument('gene', type=str, help="a mutated gene")
    parser.add_argument('classif', type=str,
                        help="the mutation classification algorithm used")
    parser.add_argument('ex_mtype', type=str)

    parser.add_argument('cohorts', type=str, nargs='+',
                        help="which TCGA cohort to use")
    parser.add_argument('--samp_cutoff', default=20,
                        help='subtype sample frequency threshold')

    args = parser.parse_args()
    out_tag = "{}__samps-{}".format('__'.join(args.cohorts), args.samp_cutoff)

    out_files = glob(os.path.join(
        base_dir, out_tag, "out-data__*_{}_{}.p".format(
            args.classif, args.ex_mtype)
        ))

    out_list = [pickle.load(open(out_file, 'rb'))['Infer']
                for out_file in out_files]
    all_df = pd.concat([ols['All'] for ols in out_list])
    iso_df = pd.concat([ols['Iso'] for ols in out_list])

    if not any(mtype.subtype_list()[0][0] == args.gene
               for _, mtype in all_df.index):
        raise ValueError("No mutations associated with gene {} were "
                         "included in this version of the "
                         "experiment!".format(args.gene))

    os.makedirs(os.path.join(plot_dir, out_tag, args.gene),
                exist_ok=True)
    out_mdls = [out_file.split("out-data__")[1].split(".p")[0]
                for out_file in out_files]

    # load expression and mutation data for each of the cohorts considered
    cdata_dict = {lvl: merge_cohort_data(os.path.join(base_dir, out_tag),
                                         use_lvl=lvl)
                  for lvl in [mdl.split('_{}_'.format(args.classif))[0]
                              for mdl in out_mdls]}

    cdata = tuple(cdata_dict.values())[0]
    use_samps = sorted(cdata.train_samps)

    copy_dict = {False: dict(), True: dict()}
    for norml in [False, True]:
        for coh in args.cohorts:
            copy_dict[norml][coh] = get_copies_firehose(
                coh.split('_')[0], copy_dir, discrete=False, normalize=norml)

            copy_samps = {old_smp: new_smp
                          for old_smp, new_smp in match_tcga_samples(
                              copy_dict[norml][coh].index)[0].items()
                          if new_smp in cdata.cohort_samps[coh.split('_')[0]]}

            copy_dict[norml][coh] = copy_dict[norml][coh].loc[
                copy_samps.keys(), cdata.genes]
            copy_dict[norml][coh].index = copy_samps.values()

        copy_dict[norml] = pd.concat(list(copy_dict[norml].values())).loc[
            use_samps]

    coh_stat = {
        cohort: np.array([samp in cdata.cohort_samps[cohort.split('_')[0]]
                          for samp in use_samps])
        for cohort in args.cohorts
        }

    auc_dict = {smps: {'Reg': dict(), 'Oth': dict(), 'Hld': dict()}
                for smps in ['All', 'Iso']}
    stab_dict = {'All': dict(), 'Iso': dict()}
    type_dict = dict()

    stat_dict = {
        copy_lbl: np.array(cdata.train_mut[args.gene].status(
            use_samps, MuType({
                ('Scale', 'Copy'): {('Copy', copy_lbl): None}})
            ))
        for copy_lbl in ['ShalGain', 'ShalDel']
        }

    for (coh, mtype) in all_df.index:
        if mtype.subtype_list()[0][0] == args.gene:
            if mtype not in type_dict:
                use_type = mtype.subtype_list()[0][1]

                if (isinstance(use_type, ExMcomb)
                        or isinstance(use_type, Mcomb)):
                    if len(use_type.mtypes) == 1:
                        use_subtype = tuple(use_type.mtypes)[0]
                        mtype_lvls = use_subtype.get_sorted_levels()[1:]
                    else:
                        mtype_lvls = None

                else:
                    use_subtype = use_type
                    mtype_lvls = use_type.get_sorted_levels()[1:]

                if mtype_lvls == ('Copy', ):
                    copy_type = use_subtype.subtype_list()[0][1].\
                            subtype_list()[0][0]

                    if copy_type == 'DeepGain':
                        type_dict[mtype] = 'Gain'
                    elif copy_type == 'DeepDel':
                        type_dict[mtype] = 'Loss'
                    else:
                        type_dict[mtype] = 'Other'

                else:
                    type_dict[mtype] = 'Point'

            if mtype not in auc_dict['All']['Reg']:
                for smps in ['All', 'Iso']:
                    stab_dict[smps][mtype] = dict()

                    for auc_type in ['Reg', 'Oth', 'Hld']:
                        auc_dict[smps][auc_type][mtype] = dict()

            use_gene, use_type = mtype.subtype_list()[0]
            mtype_lvls = use_type.get_sorted_levels()[1:]

            if '__'.join(mtype_lvls) in cdata_dict:
                use_lvls = '__'.join(mtype_lvls)
            elif not mtype_lvls or mtype_lvls == ('Copy', ):
                use_lvls = 'Location__Protein'

            mtype_stat = np.array(
                cdata_dict[use_lvls].train_mut.status(use_samps, mtype))
            all_vals = all_df.loc[[(coh, mtype)]].values[0]
            iso_vals = iso_df.loc[[(coh, mtype)]].values[0]

            gene_muts = cdata_dict[use_lvls].train_mut[args.gene]
            gene_mtype = MuType(gene_muts.allkey()) - ex_mtypes[args.ex_mtype]
            gene_stat = np.array(gene_muts.status(use_samps, gene_mtype))

            for tst_coh in args.cohorts:
                use_stat = coh_stat[tst_coh] & mtype_stat

                if np.sum(use_stat) >= 20:
                    stat_dict[tst_coh, mtype] = use_stat

                    stab_dict['All'][mtype][coh, tst_coh] = np.mean([
                        np.std(vals) for vals in all_vals[coh_stat[tst_coh]]])
                    stab_dict['All'][mtype][coh, tst_coh] /= np.std([
                        np.mean(vals)
                        for vals in all_vals[coh_stat[tst_coh]]
                        ])

                    stab_dict['Iso'][mtype][coh, tst_coh] = np.mean([
                        np.std(vals) for vals in iso_vals[coh_stat[tst_coh]]])
                    stab_dict['Iso'][mtype][coh, tst_coh] /= np.std([
                        np.mean(vals)
                        for vals in iso_vals[coh_stat[tst_coh]]
                        ])

                    wt_stat = coh_stat[tst_coh] & ~mtype_stat
                    wt_vals = np.concatenate(all_vals[wt_stat])
                    none_stat = coh_stat[tst_coh] & ~gene_stat
                    none_vals = np.concatenate(iso_vals[none_stat])

                    if tst_coh == coh:
                        cv_count = 30
                    else:
                        cv_count = 120

                    cur_stat = coh_stat[tst_coh] & mtype_stat
                    cur_all_vals = np.concatenate(all_vals[cur_stat])
                    cur_iso_vals = np.concatenate(iso_vals[cur_stat])

                    auc_dict['All']['Reg'][mtype][(coh, tst_coh)] = np.\
                            greater.outer(cur_all_vals, wt_vals).mean()
                    auc_dict['All']['Reg'][mtype][(coh, tst_coh)] += np.\
                            equal.outer(cur_all_vals, wt_vals).mean() / 2

                    auc_dict['Iso']['Reg'][mtype][(coh, tst_coh)] = np.\
                            greater.outer(cur_iso_vals, none_vals).mean()
                    auc_dict['Iso']['Reg'][mtype][(coh, tst_coh)] += np.\
                            equal.outer(cur_iso_vals, none_vals).mean() / 2

    plot_auc_comparisons(auc_dict, stat_dict, type_dict, args)
    for copy_norml in [False, True]:
        for use_cohort in args.cohorts:
            plot_copy_calls(use_cohort, all_df, iso_df, copy_dict, copy_norml,
                            auc_dict, stat_dict, coh_stat, type_dict, args)


if __name__ == '__main__':
    main()

