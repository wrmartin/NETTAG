
from utils import load_dataset, load_snp, null_dist_score1, FilterLCC, load_score
import pickle
from collections import defaultdict
import multiprocessing
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from scipy.stats import norm
import numpy as np




def sig_score(gene):
    gene_clust = set(cluster_results[gene])
    gene_score = 0.0
    for sp in snp_clust:
        sp_clust = set(cluster_results[sp])
        if len(sp_clust) > 0 and len(gene_clust) > 0:
            gene_score += len(gene_clust.intersection(sp_clust)) / len(sp_clust)

    rand_mean, rand_std = null_dist_score1(non_snp_genes, 1000, len(snp_clust), gene, cluster_results)
    gene_zscore = (gene_score - rand_mean) / rand_std
    if rand_std > 0:
        if 1 - norm.cdf(gene_zscore) < 0.05:
            return gene_zscore
        else:
            return 0
    else:
        return 0



if __name__ == '__main__':

    dirnet = '../data/ppi_remove_self_loop.txt'
    A, G_lcc, NODE2ID, ID2NODE, node2bin = load_dataset(dirnet)


    '''
    Step 0: SVD
    '''

    svd = TruncatedSVD(n_components=3800, n_iter=7, random_state=42)
    node_embed = svd.fit_transform(A)
    print(svd.explained_variance_ratio_.sum())
    print(node_embed.shape)

    '''
    Step 1: k-means
    '''
    kmeans = KMeans(n_clusters = 1200, random_state = 0).fit(node_embed)


    with open('../data/ID2NODE.pkl', 'rb') as handle:
        ID2NODE = pickle.load(handle)
    handle.close()

    cluster_results = defaultdict(list)
    for id in ID2NODE:
        cluster_results[str(ID2NODE[id])].append(kmeans.labels_[id])

    with open('../output/cluster_results_svd3800.pkl', 'wb') as handle:
        pickle.dump(cluster_results, handle, protocol=pickle.HIGHEST_PROTOCOL)
    handle.close()


    cluster_results_c2n = defaultdict(set)

    for n in cluster_results:
        cluster_results_c2n[cluster_results[n][0]].add(n)

    with open('../output/cluster_results_c2n_svd3800.pkl', 'wb') as handle:
        pickle.dump(cluster_results_c2n, handle, protocol=pickle.HIGHEST_PROTOCOL)
    handle.close()

    clust_index = []
    clust_size = []
    for c in cluster_results_c2n:
        clust_index.append(c)
        clust_size.append(len(cluster_results_c2n[c]))


    clust_size, clust_index = \
        zip(*sorted(zip(clust_size, clust_index), reverse = True))

    f_out = open('../output/' + "clust_size_stat_svd3800.txt", "w")
    f_out.write('clust_index' + "\t" + 'clust_size' +  "\n")
    for idx, size in zip(clust_index, clust_size):
        f_out.write(str(idx) + "\t" + str(size) + "\n")
    f_out.close()


    '''
    Step 2: get predicted scores
    '''

    CpG_island = load_snp('../data/CpG_island_AD_mapped_snps_entrez_id_v3.txt', header = True)
    CTCF = load_snp('../data/CTCF_AD_mapped_snps_entrez_id_v3.txt', header = True)
    enhancer = load_snp('../data/enhancer_AD_mapped_snps_entrez_id_v3.txt', header = True)
    eQTL = load_snp('../data/eQTL_AD_mapped_snps_entrez_id_v3.txt', header = True)
    histone = load_snp('../data/histone_AD_mapped_snps_entrez_id_v3.txt', header = True)
    open_chromatin = load_snp('../data/open_chromatin_AD_mapped_snps_entrez_id_v3.txt', header = True)
    promoter = load_snp('../data/promoter_AD_mapped_snps_entrez_id_v3.txt', header = True)
    pfr = load_snp('../data/pfr_AD_mapped_snps_entrez_id_v3.txt', header = True)
    tf = load_snp('../data/TF_AD_mapped_snps_entrez_id_v3.txt', header = True)
    #
    snp_input = dict()
    snp_input['CpG_island'] = CpG_island
    snp_input['CTCF'] = CTCF
    snp_input['enhancer'] = enhancer
    snp_input['eQTL'] = eQTL
    snp_input['histone'] = histone
    snp_input['open_chromatin'] = open_chromatin
    snp_input['promoter'] = promoter
    snp_input['pfr'] = pfr
    snp_input['tf'] = tf


    num_procs = 8

    all_genes = list(cluster_results.keys())

    gene_reg_ele_score = defaultdict(list)

    for reg_ele in snp_input:

        snp_clust = {gene: cluster_results[gene] for gene in snp_input[reg_ele] if gene in cluster_results}

        non_snp_genes = set(all_genes) - set(snp_clust.keys())

        all_genes_score_ls = []


        pool = multiprocessing.Pool(processes=num_procs)

        all_genes_score = pool.map(sig_score, all_genes)

        all_genes_score_ls.append(all_genes_score)

        filter_genes, filter_scores = FilterLCC('../data/lcc_nnG.p', all_genes, all_genes_score)

        f_out = open('../output/' + 'kmeans_svd3800' + '_' + str(reg_ele) + '_' + 'score.txt', "w")

        for gene_id, score in zip(filter_genes, filter_scores):
            f_out.write(str(gene_id) + '\t' + str(score) + '\n')
            gene_reg_ele_score[gene_id].append(score)

        f_out.close()

        pool.close()

        pool.join()



    '''
    Step 3: generate likely AD-associated genes
    '''

    CpG_island_gene_id, CpG_island_gene_score = load_score(
        '../output/kmeans_svd3800_CpG_island_score.txt')
    _, CTCF_gene_score = load_score(
        '../output/kmeans_svd3800_CTCF_score.txt')
    _, enhancer_gene_score = load_score(
        '../output/kmeans_svd3800_enhancer_score.txt')
    _, eqtl_gene_score = load_score(
        '../output/kmeans_svd3800_eQTL_score.txt')
    _, histone_gene_score = load_score(
        '../output/kmeans_svd3800_histone_score.txt')
    _, open_chromatin_gene_score = load_score(
        '../output/kmeans_svd3800_open_chromatin_score.txt')
    _, pfr_gene_score = load_score(
        '../output/kmeans_svd3800_pfr_score.txt')
    _, promoter_gene_score = load_score(
        '../output/kmeans_svd3800_promoter_score.txt')
    _, tf_gene_score = load_score(
        '../output/kmeans_svd3800_tf_score.txt')


    kmeans_integrated_score = []
    for score in zip(CpG_island_gene_score, CTCF_gene_score, enhancer_gene_score, eqtl_gene_score,
                     histone_gene_score, open_chromatin_gene_score, pfr_gene_score, promoter_gene_score,
                     tf_gene_score):
        kmeans_integrated_score.append(sum(score))




    kmeans_sig_gene_id = []
    kmeans_sig_gene_score = []
    # kmeans_sig_gene_z_score = []


    for idx in range(len(kmeans_integrated_score)):
        if kmeans_integrated_score[idx] > 0:
            kmeans_sig_gene_id.append(ID2NODE[idx])
            kmeans_sig_gene_score.append(kmeans_integrated_score[idx])

    kmeans_sig_mean = np.mean(np.array(kmeans_sig_gene_score))
    kmeans_sig_std = np.std(np.array(kmeans_sig_gene_score))
    kmeans_sig_z_score = (kmeans_sig_gene_score - kmeans_sig_mean) / kmeans_sig_std

    kmeans_sig_z_score, kmeans_sig_gene_score, kmeans_sig_gene_id = \
        zip(*sorted(zip(kmeans_sig_z_score, kmeans_sig_gene_score, kmeans_sig_gene_id), reverse=True))

    f_out = open('../output/' + "kmeans_svd3800_full_sig_predictions.txt", "w")
    f_out.write('node_id' + "\t" + 'score' + "\t" + 'z_score' + "\n")
    for gene_id, score, z_score in zip(kmeans_sig_gene_id, kmeans_sig_gene_score, kmeans_sig_z_score):
        f_out.write(str(gene_id) + "\t" + str(score) + "\t" + str(z_score) + "\n")
    f_out.close()
  
