#!/usr/bin/env python3
"""SingleCellFusion main rontine"""

from .__init__ import *

from scipy import sparse
import collections
import itertools
import sys
import pickle
import argparse

from . import basic_utils
from . import SCF_utils

def subsampling(mods_selected, settings, metas, gxc_hvftrs, p=0, n=0):
    """Do many datasets at the same time
    p - fraction of cells from each dataset to be included
    """
    if p < 1:
        metas_sub = collections.OrderedDict()
        gxc_hvftrs_sub = collections.OrderedDict()
        for mod in mods_selected: 
            # subsample meta
            if p != 0: 
                cells_included = metas[mod].index.values[np.random.rand(len(metas[mod]))<p]
            elif n != 0:
                if n > len(metas[mod]):
                    n = len(metas[mod])
                    
                cells_included = metas[mod].sample(n=n).index.values
            metas_sub[mod] = metas[mod].loc[cells_included]

            # subsample gxc_hvftrs
            if settings[mod].mod_category == 'mc':
                gxc_hvftrs_sub[mod] = gxc_hvftrs[mod][cells_included]
                logging.info("{} {} {}".format(mod, metas_sub[mod].shape, gxc_hvftrs_sub[mod].shape))
                continue

            cells_included_idx = basic_utils.get_index_from_array(gxc_hvftrs[mod].cell, cells_included)
            gxc_hvftrs_sub[mod] = GC_matrix(
                                            gxc_hvftrs[mod].gene,
                                            cells_included,
                                            gxc_hvftrs[mod].data.tocsc()[:, cells_included_idx],
                                            )
            logging.info("{} {} {}".format(mod, metas_sub[mod].shape, gxc_hvftrs_sub[mod].data.shape))
        return metas_sub, gxc_hvftrs_sub
    else:
        return metas, gxc_hvftrs


def add_args(parser):
    """
    """
    # parser.add_argument("-c", "--config_py", help="Configuration file", required=True)
    parser.add_argument("-i", "--data_dir", help='data dir', required=True)
    parser.add_argument("-o", "--outdir", help='outdir', required=True)
    parser.add_argument("-s", "--subsample_fraction", help="0~1", type=float, required=True)
    parser.add_argument("-sn", "--subsample_times", help=">1", type=int, required=True)
    return parser

def main(args):

    # normal
    subsample_fraction = args.subsample_fraction
    subsample_times = args.subsample_times

    # to fix
    # dir_path = os.path.dirname(os.path.realpath(__file__))
    data_dir = args.data_dir # os.path.join(dir_path, '../../data')
    outdir   = args.outdir # os.path.join(dir_path, '../../results')
    ka_smooth = 30 
    knn = 30
    date = 211115

    # # Configs  
    name = 'mop_rna_mc_ka{}_knn{}_{}'.format(ka_smooth, knn, date,)
    output_pcX_all = outdir + '/pcX_all_{}.npy'.format(name)
    output_cells_all = outdir + '/cells_all_{}.npy'.format(name) 
    output_imputed_data_format = outdir + '/imputed_data_{}_{{}}.npy'.format(name)

    save_knn = True # new required arguments (7/27/2020) 
    output_knn_within = outdir + "/knn_within_{}_{{}}.npz".format(name)
    output_knn_across = outdir + "/knn_across_{}_{{}}_{{}}.npz".format(name)
    # end of new required arguments (7/27/2020)

    # required for downsamp (8/7/2020)
    output_cells = outdir + "/cells_{{}}_{}.npy".format(name)

    meta_f = os.path.join(data_dir, '{0}_metadata.tsv')
    hvftrs_f = os.path.join(data_dir, '{0}_hvfeatures.{1}')
    hvftrs_gene = os.path.join(data_dir, '{0}_hvfeatures.gene')
    hvftrs_cell = os.path.join(data_dir, '{0}_hvfeatures.cell')

    mods_selected = [
        'mc',
        'rna',
        ]

    features_selected = ['mc']
    # check features
    for features_modality in features_selected:
        assert (features_modality in mods_selected)

    # within modality
    ps = {'mc': 0.9,
        'atac': 0.1,
        'rna': 0.7,
        }
    drop_npcs = {
        'mc': 0,
        'atac': 0,
        'rna': 0,
        }
    ka_smooth = ka_smooth # default: 5

    # across modality
    cross_mod_distance_measure = 'correlation' # cca
    knn = knn 
    relaxation = 3
    n_cca = 30

    # PCA
    npc = 50

    # clustering
    k = 30 # default: 30
    resolutions = [0.1, 1, 2, 4]
    # umap
    umap_neighbors = 60
    min_dist = 0.5

    # meta settings
    mods = (
        'mc',
        'atac',
        'rna',
    )

    Mod_info = collections.namedtuple('Mod_info', [
        'mod', 
        # 'name',
        'mod_category',
        'norm_option',
        'mod_direction', # +1 or -1
        'cell_col',
        # 'cluster_col', 
        # 'annot_col', 
        # 'category_col', # neuron or not
        'global_mean', # in general or mch
        'global_mean_mcg', # only for mcg
        # 'total_reads',
        # 'color',
        # 'species',
    ])

    # settngs
    settings_mc = Mod_info(
        mods[0],
        # 'DNA methylation',
        'mc',
        'mc', 
        -1, # negative direction 
        'cell',
        # 'SubCluster',
        # 'SubCluster', #'major_clusters' 'sub_cluster' 
        # 'SubCluster',
        'CH_Rate',
        'CG_Rate',
        # 'FinalReads',
        # 'C5',
        # 'mouse',
    )

    settings_atac = Mod_info(
        mods[1],
        # 'ATAC Seq',
        'atac',
        'tpm', 
        +1, # direction 
        'cell',
        # 'cluster',
        # 'cluster',
        # 'cluster',
        '',
        '',
        # '',
        # 'C2',
        # 'mouse',
    )

    settings_rna = Mod_info(
        mods[2],
        # '10X V3 cells',
        'rna',
        'cpm', 
        +1, # direction 
        'cell',
        # 'cluster_id',
        # 'cluster_label',
        # 'class_label',
        '',
        '',
        # '',
        # 'C6',
        # 'mouse',
    )

    settings = collections.OrderedDict({
        mods[0]: settings_mc,
        mods[1]: settings_atac,
        mods[2]: settings_rna,
    })



    ####!!actually parse things -- instead of import config.py
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    # end of configurations

    ### ---- fixed after ----
    # ## Read in data 
    logging.info('* Begin integration')

    metas = collections.OrderedDict()
    for mod in mods_selected:
        metas[mod] = pd.read_csv(meta_f.format(mod), sep="\t").reset_index().set_index(settings[mod].cell_col)
        logging.info("Metadata {} {}".format(mod, metas[mod].shape))

    gxc_hvftrs = collections.OrderedDict()
    for mod in mods_selected:
        if settings[mod].mod_category == 'mc':
            f_mat = hvftrs_f.format(mod, 'tsv')
            gxc_hvftrs[mod] = pd.read_csv(f_mat, sep='\t', header=0, index_col=0) 
            logging.info("Feature matrix {} {}".format(mod, gxc_hvftrs[mod].shape))
            assert np.all(gxc_hvftrs[mod].columns.values == metas[mod].index.values) # make sure cell name is in the sanme order as metas (important if save knn mat)
            continue
            
        f_mat = hvftrs_f.format(mod, 'npz')
        f_gene = hvftrs_gene.format(mod)
        f_cell = hvftrs_cell.format(mod)
        _gxc_tmp = basic_utils.load_gc_matrix(f_gene, f_cell, f_mat)
        _gene = _gxc_tmp.gene
        _cell = _gxc_tmp.cell
        _mat = _gxc_tmp.data

        gxc_hvftrs[mod] = GC_matrix(_gene, _cell, _mat)
        assert np.all(gxc_hvftrs[mod].cell == metas[mod].index.values) # make sure cell name is in the sanme order as metas (important if save knn mat)
        logging.info("Feature matrix {} {}".format(mod, gxc_hvftrs[mod].data.shape))
    logging.info('Done reading data')


    # subsampling 80% of cells from each modality
    for i in range(subsample_times):
        output_tag = ".{}".format(i)

        logging.info("Subsampling {}/{}".format(i+1, subsample_times))
        metas_sub, gxc_hvftrs_sub = subsampling(
                    mods_selected, settings, metas, gxc_hvftrs, p=subsample_fraction,
                    )
        for mod in mods_selected:
            fout = (output_cells+output_tag).format(mod)
            cells_mod = metas_sub[mod].index.values
            np.save(fout, cells_mod)

        # ## run SCF
        pcX_all, cells_all = SCF_utils.core_scf_routine(mods_selected, features_selected, settings, 
                                                        metas_sub, gxc_hvftrs_sub, # sub 
                                                        ps, drop_npcs,
                                                        cross_mod_distance_measure, knn, relaxation, n_cca,
                                                        npc,
                                                        output_pcX_all+output_tag, output_cells_all+output_tag,
                                                        output_imputed_data_format+output_tag,
                                                        ka_smooth=ka_smooth,
                                                        save_knn=save_knn,
                                                        output_knn_within=output_knn_within+output_tag,
                                                        output_knn_across=output_knn_across+output_tag,
                                                        )
        logging.info('Done integration into a common PC space')

    return 

if __name__ == '__main__':
    log = basic_utils.create_logger()

    parser = argparse.ArgumentParser()
    add_args(parser)
    args = parser.parse_args()
    main(args)
