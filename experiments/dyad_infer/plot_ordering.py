
import os
import sys

base_dir = os.path.join(os.environ['DATADIR'], 'HetMan', 'dyad_infer')
sys.path.extend([os.path.join(os.path.dirname(__file__), '../../..')])
plot_dir = os.path.join(base_dir, 'plots', 'ordering')

from HetMan.experiments.dyad_infer import *
from HetMan.experiments.utilities import simil_cmap

import argparse
from pathlib import Path
import dill as pickle
import bz2

import numpy as np
import pandas as pd
from functools import reduce
from operator import or_
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, dendrogram

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns


def plot_similarity_ranking(use_mtypes, stat_dict, siml_dict, args):
    mtype_list = reduce(or_, [set(mtypes) for mtypes in use_mtypes])
    siml_mat = pd.DataFrame(np.nan, index=mtype_list, columns=mtype_list)

    fig_size = 4.1 + siml_mat.shape[0] / 11
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))

    for mtypes in use_mtypes:
        siml_mat.loc[mtypes] = siml_dict[mtypes].loc['Other', 'Mtype1']
        siml_mat.loc[mtypes[::-1]] = siml_dict[mtypes].loc['Other', 'Mtype2']

    siml_rank = siml_mat.mean(axis=1) - siml_mat.mean(axis=0)
    siml_order = siml_rank.sort_values().index
    siml_mat = siml_mat.loc[siml_order, siml_order]

    for mtype in mtype_list:
        siml_mat.loc[mtype, mtype] = 1.

    # draw the heatmap
    ax = sns.heatmap(siml_mat, cmap=simil_cmap, vmin=-1., vmax=2.,
                     linewidth=0, square=True)

    # configure the tick labels on the colourbar
    cbar = ax.collections[-1].colorbar
    cbar.set_ticks([-0.5, 0.0, 0.5, 1.0, 1.5])
    cbar.set_ticklabels([
        'M2 < WT', 'M2 = WT', 'WT < M2 < M1', 'M2 = M1', 'M2 > M1'])
    cbar.ax.tick_params(labelsize=fig_size * 0.89)

    # configure the tick labels on the heatmap proper
    plt.xticks(rotation=27, ha='right', size=fig_size * 0.53)
    plt.yticks(size=fig_size * 0.67)

    plt.xlabel("M2: Testing Mutation", size=fig_size * 1.9, weight='semibold')
    plt.ylabel("M1: Training Mutation",
               size=fig_size * 1.9, weight='semibold')

    plt.savefig(os.path.join(plot_dir, args.cohort,
                             "simil-rank_{}.svg".format(args.classif)),
                bbox_inches='tight', format='svg')

    plt.close()


def plot_similarity_clustering(use_mtypes, stat_dict, siml_dict, args):
    mtype_list = reduce(or_, [set(mtypes) for mtypes in use_mtypes])
    siml_mat = pd.DataFrame(np.nan, index=mtype_list, columns=mtype_list)

    fig_size = 4.1 + siml_mat.shape[0] / 11
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))

    for mtypes in use_mtypes:
        siml_mat.loc[mtypes] = siml_dict[mtypes].loc['Other', 'Mtype1']
        siml_mat.loc[mtypes[::-1]] = siml_dict[mtypes].loc['Other', 'Mtype2']

    for mtype in mtype_list:
        siml_mat.loc[mtype, mtype] = 1.

    dist_mat = np.zeros(siml_mat.shape)
    for i in range(siml_mat.shape[0] - 1):
        for j in range(i + 1, siml_mat.shape[0]):
            dist_val = (siml_mat.iloc[i] - siml_mat.iloc[j]).abs().mean()

            dist_mat[i, j] = dist_val
            dist_mat[j, i] = dist_val

    while np.any(np.isnan(dist_mat)):
        rmv_indx = np.isnan(dist_mat).sum(axis=0).argmax()

        dist_mat = np.delete(dist_mat, rmv_indx, axis=0)
        siml_mat = siml_mat.drop(siml_mat.index[rmv_indx], axis=0)
        dist_mat = np.delete(dist_mat, rmv_indx, axis=1)
        siml_mat = siml_mat.drop(siml_mat.columns[rmv_indx], axis=1)

    row_order = dendrogram(linkage(
        squareform(dist_mat), method='centroid'))['leaves']
    siml_mat = siml_mat.iloc[row_order, row_order]

    # draw the heatmap
    ax = sns.heatmap(siml_mat, cmap=simil_cmap, vmin=-1., vmax=2.,
                     linewidth=0, square=True)

    # configure the tick labels on the colourbar
    cbar = ax.collections[-1].colorbar
    cbar.set_ticks([-0.5, 0.0, 0.5, 1.0, 1.5])
    cbar.set_ticklabels([
        'M2 < WT', 'M2 = WT', 'WT < M2 < M1', 'M2 = M1', 'M2 > M1'])
    cbar.ax.tick_params(labelsize=fig_size * 0.89)

    # configure the tick labels on the heatmap proper
    plt.xticks(rotation=27, ha='right', size=fig_size * 0.53)
    plt.yticks(size=fig_size * 0.67)

    plt.xlabel("M2: Testing Mutation", size=fig_size * 1.9, weight='semibold')
    plt.ylabel("M1: Training Mutation",
               size=fig_size * 1.9, weight='semibold')

    plt.savefig(os.path.join(plot_dir, args.cohort,
                             "simil-cluster_{}.svg".format(args.classif)),
                bbox_inches='tight', format='svg')

    plt.close()


def main():
    parser = argparse.ArgumentParser(
        "Plots the structure across the inferred similarities of pairs of "
        "mutations tested in a given experiment."
        )

    parser.add_argument('cohort', help='a TCGA cohort')
    parser.add_argument('classif', help='a mutation classifier')

    # parse command line arguments, create directory where plots will be saved
    args = parser.parse_args()
    os.makedirs(os.path.join(plot_dir, args.cohort), exist_ok=True)

    use_ctf = min(
        int(out_file.parts[-2].split('__samps-')[1])
        for out_file in Path(base_dir).glob(
            "{}__samps-*/out-data__{}.p.gz".format(args.cohort, args.classif))
        )
    out_tag = "{}__samps-{}".format(args.cohort, use_ctf)

    # load inferred mutation relationship metrics generated by the experiment
    with bz2.BZ2File(os.path.join(base_dir, out_tag,
                                  "out-simil__{}.p.gz".format(args.classif)),
                     'r') as f:
        stat_dict, auc_dict, mutex_dict, siml_dict = pickle.load(f)

    # find mutation pairs for which the classifier was able to successfully
    # predict the presence of each mutation in isolation from the other
    auc_df = (pd.DataFrame(auc_dict) >= 0.8).all(axis=0)
    use_mtypes = auc_df.index[auc_df]

    plot_similarity_ranking(use_mtypes, stat_dict, siml_dict, args)
    plot_similarity_clustering(use_mtypes, stat_dict, siml_dict, args)


if __name__ == '__main__':
    main()

