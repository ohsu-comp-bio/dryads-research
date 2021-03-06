#!/bin/bash

#SBATCH --job-name=transfer-baseline
#SBATCH --partition=exacloud
#SBATCH --verbose

#SBATCH --mem=5000
#SBATCH --time=500


export BASEDIR=HetMan/experiments/transfer_baseline
source activate HetMan

while getopts e:t:s:c:m: var
do
	case "$var" in
		e)	export expr_source=$OPTARG;;
		s)	export samp_cutoff=$OPTARG;;
		c)	export classif=$OPTARG;;
		m)	export test_max=$OPTARG;;
		[?])	echo "Usage: $0 [-e] expression source directory" \
			     "[-s] minimum sample cutoff [-c] transfer classifier" \
			     "[-m] maximum tests per node";
			exit 1;;
	esac
done

export OUTDIR=$BASEDIR/output/${expr_source}__samps-${samp_cutoff}/$classif
rm -rf $OUTDIR
mkdir -p $OUTDIR/slurm

if [ ! -e $BASEDIR/setup/combs-list_${expr_source}__samps-${samp_cutoff}.p ]
then
	srun python $BASEDIR/setup_tests.py $expr_source $samp_cutoff
fi

combs_count=$(cat $BASEDIR/setup/combs-count_${expr_source}__samps-${samp_cutoff}.txt)
export array_size=$(( ($combs_count / $test_max + 1) * 25 - 1 ))

if [ $array_size -gt 299 ]
then
	export array_size=299
fi

sbatch --output=${slurm_dir}/transfer-baseline-fit.out \
	--error=${slurm_dir}/transfer-baseline-fit.err \
	--exclude=exanode-3-3 \
	--array=0-$((array_size)) $BASEDIR/fit_tests.sh

