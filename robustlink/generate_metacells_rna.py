#!/usr/bin/env python
# coding: utf-8

from multiprocessing import Pool,cpu_count
import argparse
import os

import numpy as np
import logging
import fbpca
import itertools
import argparse
import anndata

from robustlink import utils
from scf import clst_utils
from scf import basic_utils

def pipe_singlemod_clustering(
        f_ann,
        flist_selected_cells, flist_res,
        resolutions,
        npc=50,
        kforleiden=30,
    ):
    """
    """
    # read input
    adata = anndata.read(f_ann) 
    gc_mat = basic_utils.gc_matrix_from_anndata(adata)

    for f_selected_cells, f_res in zip(flist_selected_cells, flist_res):
        print("processing {}".format(f_selected_cells))
        selected_cells = np.load(f_selected_cells, allow_pickle=True)
        # trim the matrix
        cg_mat_dense = gc_mat.data.T.todense()
        cg_mat_dense = cg_mat_dense[utils.get_index_from_array(gc_mat.cell, selected_cells)]

        # Louvain clustering for different resolutions
        # X should be selected from highly variable genes and normalized
        U, s, Vt = fbpca.pca(cg_mat_dense, k=npc)
        pcX = U.dot(np.diag(s))

        res_clsts = clst_utils.clustering_routine_multiple_resolutions(
                            pcX, selected_cells, kforleiden, 
                            seed=1, verbose=True,
                            resolutions=resolutions, metric='euclidean', option='plain', 
                            n_trees=10, search_k=-1, num_starts=None
                            )

        # organize and save results
        print(f_res)
        res_clsts.to_csv(f_res, sep='\t', na_rep='NA', header=True, index=True)
    return 

def wrapper_singlemod_clustering(
        f_ann,
        out_dir, knns, subsample_times, 
        input_name_tag,
        resolutions=[1],
    ):
    """
    """
    # input data
    shortname = os.path.basename(f_ann)
    assert shortname.endswith('.h5ad')
    shortname = shortname[:-len('.h5ad')]

    # input cell lists
    flist_selected_cells = [os.path.join(out_dir, 
            f'cells'       + f'_{input_name_tag.format(knn)}_{shortname}.{i_sub}.npy')
            for knn, i_sub in itertools.product(knns, np.arange(subsample_times))
        ]
    # output files
    flist_res = [os.path.join(out_dir, 
            f'clusterings' + f'_{input_name_tag.format(knn)}_{shortname}.{i_sub}.tsv.gz')
            for knn, i_sub in itertools.product(knns, np.arange(subsample_times))
        ]

    npc = 50
    kforleiden = 30
    pipe_singlemod_clustering(
        f_ann,
        flist_selected_cells, flist_res,
        resolutions,
        npc=npc,
        kforleiden=kforleiden,
    )
    return 

def add_args(parser):
    """
    """
    parser.add_argument("-i", "--input_dataset", help="input dataset; h5ad file", required=True)
    parser.add_argument("-o", "--out_dir", help="output result directory", required=True)
    parser.add_argument("-ks", "--knns", help="a list of knns", nargs="+", required=True)
    parser.add_argument("-sn", "--subsample_times", help=">1", type=int, required=True)
    parser.add_argument("-tag", "--input_name_tag", help="input_name_tag", required=True)
    parser.add_argument("-r", "--resolutions", nargs='+', help="Leiden clustering resolutions", required=True)
    return 

def main(args):
    """
    """
    # output setting
    # run this with each combination of (i_sub, knn)
    dataset = args.input_dataset
    assert dataset.endswith('.h5ad')
    out_dir = args.out_dir
    knns = np.array(args.knns).astype(int)
    subsample_times = args.subsample_times
    input_name_tag = args.input_name_tag
    resolutions = args.resolutions
    if isinstance(resolutions, str):
        resolutions = [int(resolutions)]
    elif isinstance(resolutions, list):
        resolutions = [int(r) for r in resolutions]

    wrapper_singlemod_clustering(
        dataset,
        out_dir, knns, subsample_times, input_name_tag,
        resolutions=resolutions,
    )

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    add_args(parser)
    args = parser.parse_args()
    main(args)
