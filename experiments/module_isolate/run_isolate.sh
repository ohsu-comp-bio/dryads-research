#!/bin/bash

#SBATCH --job-name=module-isolate
#SBATCH --partition=exacloud
#SBATCH --verbose

#SBATCH --mem=1000
#SBATCH --time=500


export BASEDIR=HetMan/experiments/module_isolate
source activate HetMan

gene_list=()
while getopts t:g:c:s:l:m: var
do
	case "$var" in
		t)	export cohort=$OPTARG;;
		g)	gene_list+=($OPTARG);;
		c)	export classif=$OPTARG;;
		s)	export samp_cutoff=$OPTARG;;
		l)	export mut_levels=$OPTARG;;
		m)	test_max=$OPTARG;;
		[?])	echo "Usage: $0 [-t] TCGA cohort [-g]...[-g] mutated genes" \
			     "[-c] mutation classifier [-s] minimum sample cutoff" \
			     "[-l] mutation annotation levels" \
			     "[-m] maximum tests per node";
			exit 1;;
	esac
done

echo "Starting gene module subvariant isolation experiment in TCGA cohort "${cohort} \
     "with genes "${gene_list[@]}" using classifier "${classif}" and a sample cutoff" \
     "of "${samp_cutoff}", mutation annotation levels "${mut_levels}", and a maximum" \
     "of "${test_max}" tests per compute node."

IFS=$'\n'
export sorted_genes=($(sort <<<"${gene_list[*]}"))
unset IFS
export gene_lbl=$(IFS='_'; echo "${sorted_genes[*]}")

# get the directory where the experiment results will be saved, removing it
# if it already exists
export OUTDIR=$BASEDIR/output/$cohort/${gene_lbl}/$classif/samps_${samp_cutoff}/$mut_levels
rm -rf $OUTDIR
mkdir -p $OUTDIR/slurm

# setup the experiment by finding a list of mutation subtypes to be tested
if [ ! -e ${BASEDIR}/setup/${cohort}/${gene_lbl}/mtypes_list__samps_${samp_cutoff}__levels_${mut_levels}.p ]
then

	srun -p=exacloud \
		--output=$BASEDIR/setup/slurm_${cohort}.txt \
		--error=$BASEDIR/setup/slurm_${cohort}.err \
		python $BASEDIR/setup_isolate.py -v \
		$cohort $mut_levels "${sorted_genes[@]}" --samp_cutoff=$samp_cutoff
fi

# find how large of a batch array to submit based on how many mutation types were
# found in the setup enumeration
mtypes_count=$(cat ${BASEDIR}/setup/${cohort}/${gene_lbl}/mtypes_count__samps_${samp_cutoff}__levels_${mut_levels}.txt)
export array_size=$(( $mtypes_count / $test_max ))

if [ $array_size -gt 299 ]
then
	export array_size=299
fi

# run the subtype tests in parallel
sbatch --output=${slurm_dir}/module-iso_fit.out \
	--error=${slurm_dir}/module-iso_fit.err \
	--exclude=$ex_nodes --no-requeue \
	--array=0-$(( $array_size )) $BASEDIR/fit_isolate.sh

