
import os
import sys

base_dir = os.path.join(os.environ['DATADIR'], 'HetMan', 'copy_baseline')
sys.path.extend([os.path.join(os.path.dirname(__file__), '../../..')])
plot_dir = os.path.join(base_dir, 'plots', 'tuning')

from HetMan.experiments.copy_baseline import *
from HetMan.experiments.variant_baseline.merge_tests import merge_cohort_data
from HetMan.experiments.variant_baseline.plot_experiment import (
    detect_log_distr)
from HetMan.experiments.utilities.colour_maps import cor_cmap
from HetMan.experiments.utilities.scatter_plotting import place_annot

import argparse
from pathlib import Path
import bz2
import dill as pickle

import numpy as np
import pandas as pd
from itertools import product

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

plt.style.use('fivethirtyeight')
plt.rcParams['axes.facecolor']='white'
plt.rcParams['savefig.facecolor']='white'
plt.rcParams['axes.edgecolor']='white'


def plot_generalization_error(train_cors, test_cors, args):
    plot_min = min(train_cors.min().min(), test_cors.min().min()) - 0.01

    if np.min(train_cors.values) > 0.999:
        train_cors += np.random.randn(train_cors.shape[1]) / 500

    g = sns.JointGrid(train_cors.values.flatten(), test_cors.values.flatten(),
                      xlim=(plot_min, 1.01), ylim=(plot_min, 1.01), height=9)
    g = g.plot_joint(sns.kdeplot,
                     shade=True, shade_lowest=False, bw=0.01, cut=0)
    g = g.plot_marginals(sns.distplot, kde=False)

    g.ax_joint.tick_params(pad=3.9)
    g.ax_joint.plot([-1, 2], [-1, 2],
                    linewidth=1.7, linestyle='--', color='#550000', alpha=0.6)

    g.ax_joint.set_xlabel('Training Correlation',
                          fontsize=22, weight='semibold')
    g.ax_joint.set_ylabel('Testing Correlation',
                          fontsize=22, weight='semibold')

    g.savefig(
        os.path.join(plot_dir, '__'.join([args.expr_source, args.cohort]),
                     args.model_name.split('__')[0],
                     "{}__generalization.svg".format(
                         args.model_name.split('__')[1])),
        dpi=300, bbox_inches='tight', format='svg'
        )

    plt.close()


def plot_tuning_distribution(par_df, cor_df, use_clf, args, cdata):
    fig, axarr = plt.subplots(
        figsize=(17, 0.3 + 7 * len(use_clf.tune_priors)),
        nrows=len(use_clf.tune_priors), ncols=1, squeeze=False
        )

    cor_vals = cor_df.values.flatten()
    par_df = par_df.iloc[:, :-len(use_clf.tune_priors)]

    for ax, (par_name, tune_distr) in zip(axarr.flatten(),
                                          use_clf.tune_priors):
        ax.set_title(par_name, size=29, weight='semibold')

        use_df = pd.DataFrame({'Acc': cor_vals,
                               'Par': par_df[par_name].values.flatten()})
        use_df['Acc'] += np.random.normal(loc=0.0, scale=1e-4,
                                          size=use_df.shape[0])
 
        sns.violinplot(data=use_df, x='Par', y='Acc', ax=ax, order=tune_distr,
                       cut=0, scale='count', linewidth=1.7)

        ax.axhline(y=0, color='#550000', linewidth=2.9, alpha=0.32)
        ax.set_xticklabels(['{:.1e}'.format(par) for par in tune_distr])

        ax.tick_params(labelsize=18)
        ax.set_xlabel("")
        ax.set_ylabel("")
 
        ax.tick_params(axis='x', labelrotation=38)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment('right')

    ax.set_xlabel("Tuned Hyper-Parameter Value", size=26, weight='semibold')
    fig.text(-0.01, 0.5, 'Correlation', ha='center', va='center',
             fontsize=26, weight='semibold', rotation='vertical')

    fig.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, '__'.join([args.expr_source, args.cohort]),
                     args.model_name.split('__')[0],
                     "{}__tuning-distribution.svg".format(
                         args.model_name.split('__')[1])),
        dpi=300, bbox_inches='tight', format='svg'
        )

    plt.close()


def plot_tuning_profile(tune_dict, use_clf, args, cdata):
    fig, axarr = plt.subplots(
        figsize=(17, 0.3 + 7 * len(use_clf.tune_priors)),
        nrows=len(use_clf.tune_priors), ncols=1, squeeze=False
        )

    tune_df = tune_dict['mean'] - tune_dict['std']
    tune_df.columns.names = [par for par, _ in use_clf.tune_priors]
    tune_df = tune_df.groupby(
        axis=1, level=tune_df.columns.names).quantile(q=0.25)

    for ax, (par_name, tune_distr) in zip(axarr.flatten(),
                                          use_clf.tune_priors):
        if len(tune_df.columns.names) > 1:
            tune_vals = tune_df.groupby(axis=1, level=par_name).mean()
        else:
            tune_vals = tune_df

        if detect_log_distr(tune_distr):
            use_distr = [np.log10(par_val) for par_val in tune_distr]
            par_lbl = par_name + '\n(log-scale)'

        else:
            use_distr = tune_distr
            par_lbl = par_name

        ax.axhline(color='#550000', y=0, linewidth=3.1, alpha=0.32)
        ax.set_xlabel(par_lbl, fontsize=22, weight='semibold')
        ax.set_ylabel('Training Correlation', fontsize=22, weight='semibold')

        for vals in tune_vals.values:
            ax.plot(use_distr, vals, '-',
                    linewidth=1.3, alpha=0.23, color=cor_cmap(np.max(vals)))

        for par_val in use_distr:
            ax.axvline(x=par_val, color='#116611',
                       ls=':', linewidth=1.3, alpha=0.16)

    fig.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, '__'.join([args.expr_source, args.cohort]),
                     args.model_name.split('__')[0],
                     "{}__tuning-profile.svg".format(
                         args.model_name.split('__')[1])),
        dpi=300, bbox_inches='tight', format='svg'
        )

    plt.close()


def plot_tuning_profile_grid(tune_dict, use_clf, args, cdata):
    fig, axarr = plt.subplots(
        figsize=(0.1 + 2.3 * len(use_clf.tune_priors[1][1]),
                 0.1 + 2.3 * len(use_clf.tune_priors[0][1])),
        nrows=len(use_clf.tune_priors[0][1]),
        ncols=len(use_clf.tune_priors[1][1]),
        sharex=True, sharey=True
        )

    tune_grps = (tune_dict['mean'] - tune_dict['std']).groupby(
        axis=1, level=tune_dict['mean'].columns.names)
    ylim = max(tune_grps.min().values.min(), 0)
    mtype_order = tune_grps.quantile(q=0.25).max(axis=1).sort_values(
        ascending=False).index

    for (i, par_val1), (j, par_val2) in product(
            enumerate(use_clf.tune_priors[0][1]),
            enumerate(use_clf.tune_priors[1][1])
            ):

        if i == 0:
            axarr[i, j].text(0.5, 1.03, format(par_val2, '.1g'),
                             size=16, weight='semibold', ha='center',
                             va='bottom', transform=axarr[i, j].transAxes)

        if j == 0:
            axarr[i, j].text(-0.24, 0.5, format(par_val1, '.1g'),
                             size=16, weight='semibold', rotation=90,
                             ha='right', va='center',
                             transform=axarr[i, j].transAxes)

        axarr[i, j].plot(
            tune_grps.quantile(q=0.25).loc[
                mtype_order, (par_val1, par_val2)].values,
            linewidth=3.1, color='blue', alpha=0.9
            )

        axarr[i, j].fill_between(
            list(range(len(mtype_order))),
            y1=tune_grps.quantile(q=0.5).loc[
                mtype_order, (par_val1, par_val2)].values,
            y2=tune_grps.min().loc[mtype_order, (par_val1, par_val2)].values,
            facecolor='blue', alpha=0.3, interpolate=True
            )

        axarr[i, j].set_xticks([])
        axarr[i, j].set_ylim(ylim, 1.01)

    fig.text(0.5, 60/59, use_clf.tune_priors[1][0],
             size=21, weight='semibold', ha='center', va='bottom')
    fig.text(-0.03, 0.5, use_clf.tune_priors[0][0], size=21,
             weight='semibold', rotation=90, ha='right', va='center')

    fig.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, '__'.join([args.expr_source, args.cohort]),
                     args.model_name.split('__')[0],
                     "{}__tuning-profile-grid.svg".format(
                         args.model_name.split('__')[1])),
        dpi=300, bbox_inches='tight', format='svg'
        )

    plt.close()


def main():
    parser = argparse.ArgumentParser(
        "Plots the performance and tuning characteristics of a model in "
        "classifying the copy number scores of the genes in a given cohort."
        )

    parser.add_argument('expr_source', type=str,
                        help="which TCGA expression data source was used")
    parser.add_argument('cohort', type=str, help="which TCGA cohort was used")
    parser.add_argument('model_name', type=str,
                        help="which mutation classifier was tested")

    args = parser.parse_args()
    os.makedirs(os.path.join(
        plot_dir, '__'.join([args.expr_source, args.cohort]),
        args.model_name.split('__')[0]
        ), exist_ok=True)

    use_ctf = min(
        int(out_file.parts[-2].split('__samps-')[1])
        for out_file in Path(base_dir).glob(
            "{}__{}__samps-*/out-data__{}.p.gz".format(
                args.expr_source, args.cohort, args.model_name)
            )
        )

    out_tag = "{}__{}__samps-{}".format(
        args.expr_source, args.cohort, use_ctf)
    cdata = merge_cohort_data(os.path.join(base_dir, out_tag))

    with bz2.BZ2File(os.path.join(base_dir, out_tag,
                                  "out-data__{}.p.gz".format(
                                      args.model_name)),
                     'r') as fl:
        out_dict = pickle.load(fl)

    plot_generalization_error(out_dict['Fit']['train'].Cor,
                              out_dict['Fit']['test'].Cor, args)
    plot_tuning_distribution(out_dict['Params'], out_dict['Fit']['test'].Cor,
                             out_dict['Clf'], args, cdata)

    plot_tuning_profile(out_dict['Tune']['Acc'], out_dict['Clf'], args, cdata)
    if len(out_dict['Clf'].tune_priors) == 2:
        plot_tuning_profile_grid(out_dict['Tune']['Acc'], out_dict['Clf'],
                                 args, cdata)


if __name__ == "__main__":
    main()

