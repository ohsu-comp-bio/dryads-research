#!/bin/bash

#SBATCH --job-name=varportray-fit
#SBATCH --partition=exacloud

#SBATCH --array=0-29
#SBATCH --time=1200
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem-per-cpu=4000

#SBATCH --output=/home/exacloud/lustre1/CompBio/mgrzad/slurm/log-files/varportray-fit_out-%A.txt
#SBATCH --error=/home/exacloud/lustre1/CompBio/mgrzad/slurm/log-files/varportray-fit_err-%A.txt
#SBATCH --verbose


# move to the working directory, find where to place output
cd ~/compbio/bergamot
TEMPDIR=HetMan/experiments/subvariant_detection/output/$cohort/$classif/portray

# disable threading on each CPU, print info about this array job
export OMP_NUM_THREADS=1
echo $cohort
echo $classif

# pause between starting array jobs to ease load when downloading -omic datasets
sleep $(($SLURM_ARRAY_TASK_ID * 17));

# get the cross-validation ID and sub-variant sub-task ID defined by this
# job's SLURM array ID
cv_id=$(($SLURM_ARRAY_TASK_ID / 3));
task_id=$(($SLURM_ARRAY_TASK_ID % 3));

# find the expression effects for the training/testing cohort split defined
# by the cross-validation ID and the sub-variant subset defined by the sub-task ID
srun -p=exacloud \
	--output=$TEMPDIR/slurm/fit-${cv_id}_${task_id}.txt \
	--error=$TEMPDIR/slurm/fit-${cv_id}_${task_id}.err \
	python HetMan/experiments/utilities/depict_cohort_mutypes.py \
	$TEMPDIR $cohort $classif $cv_id $task_id -v

