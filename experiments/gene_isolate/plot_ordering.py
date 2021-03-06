
import os
import sys

if 'DATADIR' in os.environ:
    base_dir = os.path.join(os.environ['DATADIR'],
                            'HetMan', 'subvariant_isolate')
else:
    base_dir = os.path.dirname(__file__)

plot_dir = os.path.join(base_dir, 'plots', 'ordering')
sys.path.extend([os.path.join(os.path.dirname(__file__), '../../..')])

from HetMan.experiments.subvariant_isolate.fit_isolate import load_cohort_data
from HetMan.experiments.subvariant_isolate.utils import compare_scores
from HetMan.experiments.utilities import load_infer_output, simil_cmap

import argparse
import numpy as np
import pandas as pd
from scipy.spatial import distance
from scipy.cluster.hierarchy import linkage, dendrogram

import matplotlib as mpl
mpl.use('Agg')
import seaborn as sns
import matplotlib.pyplot as plt


def plot_singleton_ordering(simil_df, auc_list, pheno_dict, args):
    singl_mcombs = [mcomb for mcomb in simil_df.index
                    if all(len(mtype.subkeys()) == 1
                           for mtype in mcomb.mtypes)]

    fig_size = 5. + len(singl_mcombs) * 0.43
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))
    simil_df = simil_df.loc[singl_mcombs, singl_mcombs]

    simil_rank = simil_df.mean(axis=1) - simil_df.mean(axis=0)
    simil_order = simil_rank.sort_values().index
    simil_df = simil_df.loc[simil_order, simil_order]

    annot_df = simil_df.copy()
    annot_df[annot_df < 3.] = 0.0
    for mcomb in singl_mcombs:
        annot_df.loc[mcomb, mcomb] = auc_list[mcomb]

    annot_df = annot_df.applymap('{:.2f}'.format).applymap(
        lambda x: ('' if x == '0.00' else '1.0' if x == '1.00'
                   else x.lstrip('0'))
        )

    xlabs = ['{}  ({})'.format(mcomb, np.sum(pheno_dict[mcomb]))
             for mcomb in simil_df.index]
    ylabs = [repr(mcomb).replace('ONLY ', '').replace(' AND ', '\nAND\n')
             for mcomb in simil_df.index]

    xlabs = [xlab.replace('Point:', '') for xlab in xlabs]
    xlabs = [xlab.replace('Copy:', '') for xlab in xlabs]
    ylabs = [ylab.replace('Scale IS Point WITH ', '') for ylab in ylabs]
    ylabs = [ylab.replace('Scale IS Copy WITH ', '') for ylab in ylabs]
    ylabs = [ylab.replace('\nScale IS Point\nWITH', '\n') for ylab in ylabs]
    ylabs = [ylab.replace('\nScale IS Copy\nWITH', '\n') for ylab in ylabs]

    # draw the heatmap
    ax = sns.heatmap(simil_df, cmap=simil_cmap, vmin=-1., vmax=2.,
                     xticklabels=xlabs, yticklabels=ylabs, square=True,
                     annot=annot_df, fmt='', annot_kws={'size': 14})

    # configure the tick labels on the colourbar
    cbar = ax.collections[-1].colorbar
    cbar.set_ticks([-0.5, 0.0, 0.5, 1.0, 1.5])
    cbar.set_ticklabels([
        'M2 < WT', 'M2 = WT', 'WT < M2 < M1', 'M2 = M1', 'M2 > M1'])
    cbar.ax.tick_params(labelsize=17)

    # configure the tick labels on the heatmap proper
    plt.xticks(rotation=27, ha='right', size=13)
    plt.yticks(size=10)

    plt.xlabel("M2: Testing Mutation (# of samples)",
               size=24, weight='semibold')
    plt.ylabel("M1: Training Mutation", size=26, weight='semibold')

    plt.savefig(os.path.join(
        plot_dir, '{}_{}'.format(args.cohort, args.gene),
        "singleton-ordering__{}__samps_{}__{}.png".format(
            args.classif, args.samp_cutoff, args.mut_levels)
            ),
        dpi=300, bbox_inches='tight'
        )

    plt.close()


def plot_singleton_clustering(simil_df, auc_list, pheno_dict, args):
    singl_mcombs = [mcomb for mcomb in simil_df.index
                    if all(len(mtype.subkeys()) == 1
                           for mtype in mcomb.mtypes)]

    fig_size = 5. + len(singl_mcombs) * 0.43
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))
    simil_df = simil_df.loc[singl_mcombs, singl_mcombs]

    row_order = dendrogram(linkage(distance.pdist(
        simil_df, metric='cityblock'), method='centroid'))['leaves']
    simil_df = simil_df.iloc[row_order, row_order]

    annot_df = simil_df.copy()
    annot_df[annot_df < 3.] = 0.0
    for mcomb in simil_df.index:
        annot_df.loc[mcomb, mcomb] = auc_list[mcomb]

    annot_df = annot_df.applymap('{:.2f}'.format).applymap(
        lambda x: ('' if x == '0.00' else '1.0' if x == '1.00'
                   else x.lstrip('0'))
        )
 
    xlabs = ['{}  ({})'.format(mcomb, np.sum(pheno_dict[mcomb]))
             for mcomb in simil_df.index]
    ylabs = [repr(mcomb).replace('ONLY ', '').replace(' AND ', '\nAND\n')
             for mcomb in simil_df.index]

    xlabs = [xlab.replace('Point:', '') for xlab in xlabs]
    xlabs = [xlab.replace('Copy:', '') for xlab in xlabs]
    ylabs = [ylab.replace('Scale IS Point WITH ', '') for ylab in ylabs]
    ylabs = [ylab.replace('Scale IS Copy WITH ', '') for ylab in ylabs]
    ylabs = [ylab.replace('\nScale IS Point\nWITH', '\n') for ylab in ylabs]
    ylabs = [ylab.replace('\nScale IS Copy\nWITH', '\n') for ylab in ylabs]

    # draw the heatmap
    ax = sns.heatmap(simil_df, cmap=simil_cmap, vmin=-1., vmax=2.,
                     xticklabels=xlabs, yticklabels=ylabs, square=True,
                     annot=annot_df, fmt='', annot_kws={'size': 14})

    # configure the tick labels on the colourbar
    ax.collections = [ax.collections[-1]]
    cbar = ax.collections[-1].colorbar
    cbar.set_ticks([-0.5, 0.0, 0.5, 1.0, 1.5])
    cbar.set_ticklabels([
        'M2 < WT', 'M2 = WT', 'WT < M2 < M1', 'M2 = M1', 'M2 > M1'])
    cbar.ax.tick_params(labelsize=17)

    # configure the tick labels on the heatmap proper
    plt.xticks(rotation=27, ha='right', size=13)
    plt.yticks(size=10)

    plt.xlabel("M2: Testing Mutation (# of samples)",
               size=22, weight='semibold')
    plt.ylabel("M1: Training Mutation", size=25, weight='semibold')

    plt.savefig(os.path.join(
        plot_dir, '{}_{}'.format(args.cohort, args.gene),
        "singleton-clustering__{}__samps_{}__{}.png".format(
            args.classif, args.samp_cutoff, args.mut_levels)
            ),
        dpi=300, bbox_inches='tight'
        )

    plt.close()


def plot_all_ordering(simil_df, auc_list, args):
    fig, ax = plt.subplots(figsize=(13, 12))

    use_mcombs = auc_list[auc_list > 0.7].index
    simil_df = simil_df.loc[use_mcombs, use_mcombs]
    simil_rank = simil_df.mean(axis=1) - simil_df.mean(axis=0)
    simil_order = simil_rank.sort_values().index
    simil_df = simil_df.loc[simil_order, simil_order]

    sns.heatmap(simil_df, cmap=simil_cmap, vmin=-1., vmax=2., ax=ax,
                xticklabels=False, square=True)

    cbar = ax.collections[0].colorbar
    cbar.set_ticks([-0.5, 0.0, 0.5, 1.0, 1.5])
    cbar.set_ticklabels([
        'M2 < WT', 'M2 = WT', 'WT < M2 < M1', 'M2 = M1', 'M2 > M1'])
    cbar.ax.tick_params(labelsize=19)

    plt.xlabel('M2: Testing Mutation', size=24, weight='semibold')
    plt.ylabel('M1: Training Mutation', size=24, weight='semibold')

    plt.savefig(os.path.join(
        plot_dir, '{}_{}'.format(args.cohort, args.gene),
        "all-ordering__{}__samps_{}__{}.png".format(
            args.classif, args.samp_cutoff, args.mut_levels)
            ),
        dpi=300, bbox_inches='tight'
        )

    plt.close()


def plot_all_clustering(simil_df, auc_list, args):
    use_mcombs = auc_list[auc_list > 0.7].index
    simil_df = simil_df.loc[use_mcombs, use_mcombs]

    simil_df.index = [str(mcomb).replace('Point:', '')
                      for mcomb in simil_df.index]
    simil_df.index = [str(mcomb).replace('Copy:', '')
                      for mcomb in simil_df.index]

    row_linkage = linkage(distance.pdist(
        simil_df, metric='cityblock'), method='centroid')
    gr = sns.clustermap(
        simil_df, cmap=simil_cmap, figsize=(12, 11), vmin=-1., vmax=2.,
        row_linkage=row_linkage, col_linkage=row_linkage, square=True
        )

    gr.ax_heatmap.set_xticks([])
    gr.cax.set_visible(False)

    plt.savefig(os.path.join(
        plot_dir, '{}_{}'.format(args.cohort, args.gene),
        "all-clustering__{}__samps_{}__{}.png".format(
            args.classif, args.samp_cutoff, args.mut_levels)
            ),
        dpi=300, bbox_inches='tight'
        )

    plt.close()


def main():
    parser = argparse.ArgumentParser(
        "Plot the ordering of a gene's subtypes in a given cohort based on "
        "how their isolated expression signatures classify one another."
        )

    parser.add_argument('cohort', help='a TCGA cohort')
    parser.add_argument('gene', help='a mutated gene')
    parser.add_argument('classif', help='a mutation classifier')
    parser.add_argument('mut_levels', default='Form_base__Exon',
                        help='a set of mutation annotation levels')
    parser.add_argument('--samp_cutoff', default=20)

    parser.add_argument('--all_mcombs', '-a', action='store_true',
                        help=("plot results for all mutation types as "
                              "opposed to just singletons"))

    # parse command line arguments, create directory where plots will be saved
    args = parser.parse_args()
    os.makedirs(os.path.join(plot_dir,
                             '{}_{}'.format(args.cohort, args.gene)),
                exist_ok=True)

    cdata = load_cohort_data(base_dir,
                             args.cohort, args.gene, args.mut_levels)
    infer_df = load_infer_output(os.path.join(
        base_dir, 'output', args.cohort, args.gene, args.classif,
        'samps_{}'.format(args.samp_cutoff), args.mut_levels
        ))

    if args.all_mcombs:
        use_mtypes = infer_df.index
    else:
        use_mtypes = [mcomb for mcomb in infer_df.index
                      if all(len(mtype.subkeys()) == 1
                             for mtype in mcomb.mtypes)]

    pheno_dict, auc_list, simil_df = compare_scores(infer_df.loc[use_mtypes],
                                                    cdata)

    plot_singleton_ordering(simil_df.copy(), auc_list.copy(),
                            pheno_dict.copy(), args)
    plot_singleton_clustering(simil_df.copy(), auc_list.copy(),
                              pheno_dict.copy(), args)

    if args.all_mcombs:
        plot_all_ordering(simil_df.copy(), auc_list.copy(), args)
        plot_all_clustering(simil_df.copy(), auc_list.copy(), args)


if __name__ == '__main__':
    main()

