
from ..subgrouping_test import base_dir
from .utils import choose_mtype_colour
from ..utilities.colour_maps import variant_clrs

import os
import argparse
import bz2
import dill as pickle

import numpy as np
import pandas as pd

import matplotlib as mpl
import matplotlib.pyplot as plt

mpl.use('Agg')
plt.style.use('fivethirtyeight')
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['savefig.facecolor'] = 'white'
plt.rcParams['axes.edgecolor'] = 'white'
plot_dir = os.path.join(base_dir, 'plots', 'experiment')


def lbl_norm(lbls, wt_val, mut_val):
    norm_diff = mut_val - wt_val

    if norm_diff == 0:
        norm_lbls = [0 for lbl in lbls]
    else:
        norm_lbls = [(lbl - wt_val) / norm_diff for lbl in lbls]

    return np.mean(norm_lbls), np.var(norm_lbls)


def plot_auc_stability(auc_vals, pheno_dict, args):
    fig, ax = plt.subplots(figsize=(13, 8))

    # calculate average and standard deviation of task AUCs across CVs
    stat_dict = pd.DataFrame({'Mean': auc_vals.apply(np.mean),
                              'Var': auc_vals.apply(np.std)})

    # plot mean and SD of AUCs for each classification task
    for mtype, mean_val in stat_dict['Mean'].iteritems():
        ax.scatter(mean_val, stat_dict['Var'][mtype],
                   facecolor=[choose_mtype_colour(mtype)],
                   s=251 * np.mean(pheno_dict[mtype]),
                   alpha=0.23, edgecolors='none')

    # get axis limits, leaving spare room on the bottom for labels
    x_lims = ax.get_xlim()
    y_lims = [-ax.get_ylim()[1] / 91, ax.get_ylim()[1]]

    ax.plot(x_lims, [0, 0], color='black', linewidth=1.6, alpha=0.71)
    ax.plot([0.5, 0.5], [0, y_lims[1]],
            color='black', linewidth=1.4, linestyle=':', alpha=0.61)

    ax.tick_params(axis='both', which='major', labelsize=17)
    plt.grid(alpha=0.37, linewidth=0.9)
    ax.set_xlim(x_lims)
    ax.set_ylim(y_lims)

    plt.xlabel("Average AUC Across CVs", fontsize=23, weight='semibold')
    plt.ylabel("AUC Standard Deviation", fontsize=23, weight='semibold')

    plt.savefig(
        os.path.join(plot_dir,
                     "{}__{}__samps-{}".format(
                         args.expr_source, args.cohort, args.samp_cutoff),
                     "auc-stability_{}__{}.svg".format(
                         args.mut_levels, args.classif)),
        bbox_inches='tight', format='svg'
        )

    plt.close()


def plot_label_stability(pred_df, auc_vals, pheno_dict, args):
    fig, axarr = plt.subplots(figsize=(15, 7), ncols=4)

    use_aucs = auc_vals.round(4)
    auc_bins = pd.qcut(use_aucs.values.flatten(),
                       q=[0., 0.5, 0.8, 0.9, 1.], precision=5).categories

    use_bins = np.array([auc_bins.get_loc(auc_val)
                         for auc_val in use_aucs[pred_df.index]])

    for auc_indx, pred_mat in pred_df.groupby(by=use_bins):
        mtype_norms = {mtype: (
            np.mean(np.concatenate(infr_vals.values[~pheno_dict[mtype]])),
            np.mean(np.concatenate(infr_vals.values[pheno_dict[mtype]]))
            ) for mtype, infr_vals in pred_mat.iterrows()}

        wt_vals = np.vstack([
            np.vstack(pred_mat.loc[mtype, ~pheno_dict[mtype]].apply(
                lambda vals: lbl_norm(vals, wt_val, mut_val)).values)
            for mtype, (wt_val, mut_val) in mtype_norms.items()
            ])

        mut_vals = np.vstack([
            np.vstack(pred_mat.loc[mtype, pheno_dict[mtype]].apply(
                lambda vals: lbl_norm(vals, wt_val, mut_val)).values)
            for mtype, (wt_val, mut_val) in mtype_norms.items()
            ])

        axarr[auc_indx].set_title(
            "{:.3f} - {:.3f}".format(auc_bins[auc_indx].left,
                                     auc_bins[auc_indx].right),
            fontsize=19
            )

        axarr[auc_indx].text(0.5, 0.99, "n={}".format(pred_mat.shape[0]),
                             size=14, ha='center', va='top',
                             transform=axarr[auc_indx].transAxes)

        qnt_pnts = np.linspace(2.5, 97.5, 190)
        wt_qnts = np.unique(np.percentile(wt_vals[:, 0], q=qnt_pnts))
        mut_qnts = np.unique(np.percentile(mut_vals[:, 0], q=qnt_pnts))

        wt_vars = np.vstack([
            np.percentile(wt_vals[(wt_vals[:, 0] >= wt_qnts[i - 3])
                                  & (wt_vals[:, 0] < wt_qnts[i + 3]), 1],
                          q=[25, 50, 75])
            for i in range(3, len(wt_qnts) - 3)
            ])

        mut_vars = np.vstack([
            np.percentile(mut_vals[(mut_vals[:, 0] >= mut_qnts[i - 3])
                                   & (mut_vals[:, 0] < mut_qnts[i + 3]), 1],
                          q=[25, 50, 75])
            for i in range(3, len(mut_qnts) - 3)
            ])

        for j, (use_lw, use_ls) in enumerate(zip([1.9, 3.1, 1.9],
                                                 [':', '-', ':'])):
            axarr[auc_indx].plot(
                wt_qnts[3:-3], wt_vars[:, j], color=variant_clrs['WT'],
                linewidth=use_lw, alpha=0.59, linestyle=use_ls
                )

            axarr[auc_indx].plot(mut_qnts[3:-3], mut_vars[:, j],
                                 color=variant_clrs['Point'],
                                 linewidth=use_lw, alpha=0.59,
                                 linestyle=use_ls)

        x_lims = axarr[auc_indx].get_xlim()
        y_lims = [-axarr[auc_indx].get_ylim()[1] / 91,
                  axarr[auc_indx].get_ylim()[1]]

        axarr[auc_indx].plot(x_lims, [0, 0],
                             color='black', linewidth=1.6, alpha=0.71)

        axarr[auc_indx].tick_params(axis='both', which='major', labelsize=13)
        axarr[auc_indx].grid(alpha=0.37, linewidth=0.9)
        axarr[auc_indx].set_xlim(x_lims)
        axarr[auc_indx].set_ylim(y_lims)

    fig.text(0.5, 0, "Mean Sample Score",
             fontsize=23, weight='semibold', ha='center', va='top')
    fig.text(-1 / 137, 0.5, "Sample Score SD",
             fontsize=23, weight='semibold', rotation=90,
             ha='center', va='center')

    fig.text(1 / 23, 0.95, "AUC Bins",
             fontsize=15, weight='semibold', ha='right', va='center')

    fig.tight_layout(w_pad=2.3, h_pad=1.9)
    plt.savefig(
        os.path.join(plot_dir,
                     "{}__{}__samps-{}".format(
                         args.expr_source, args.cohort, args.samp_cutoff),
                     "label-stability_{}__{}.svg".format(
                         args.mut_levels, args.classif)),
        bbox_inches='tight', format='svg'
        )

    plt.close()


def main():
    parser = argparse.ArgumentParser(
        'plot_experiment',
        description="Plots general diagnostics about a single experiment run."
        )

    parser.add_argument('expr_source', help="a source of expression datasets")
    parser.add_argument('cohort', help="a TCGA cohort", type=str)
    parser.add_argument('samp_cutoff',
                        help="a mutation frequency cutoff", type=int)

    parser.add_argument('mut_levels',
                        help="a set of mutation annotation levels", type=str)
    parser.add_argument('classif', help="a mutation classifier", type=str)

    args = parser.parse_args()
    out_tag = "{}__{}__samps-{}".format(
        args.expr_source, args.cohort, args.samp_cutoff)

    with bz2.BZ2File(os.path.join(base_dir, out_tag,
                                  "cohort-data__{}__{}.p.gz".format(
                                      args.mut_levels, args.classif)),
                     'r') as f:
        cdata = pickle.load(f)

    with bz2.BZ2File(os.path.join(base_dir, out_tag,
                                  "out-pheno__{}__{}.p.gz".format(
                                      args.mut_levels, args.classif)),
                     'r') as f:
        pheno_dict = pickle.load(f)

    with bz2.BZ2File(os.path.join(base_dir, out_tag,
                                  "out-pred__{}__{}.p.gz".format(
                                      args.mut_levels, args.classif)),
                     'r') as f:
        pred_df = pickle.load(f)

    with bz2.BZ2File(os.path.join(base_dir, out_tag,
                                  "out-aucs__{}__{}.p.gz".format(
                                      args.mut_levels, args.classif)),
                     'r') as f:
        auc_df = pickle.load(f)

    os.makedirs(os.path.join(plot_dir, out_tag), exist_ok=True)
    plot_auc_stability(auc_df['CV'], pheno_dict, args)
    if len(pheno_dict) >= 50:
        plot_label_stability(pred_df, auc_df['mean'], pheno_dict, args)


if __name__ == '__main__':
    main()

