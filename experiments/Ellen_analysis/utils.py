
from pathlib import Path
from dryadic.features.cohorts.utils import log_norm
import numpy as np
import pandas as pd


def load_ellen_expression(expr_file):
    return log_norm(pd.read_csv(expr_file, sep='\t', index_col=0).transpose())

    ellen_expr = ellen_expr.apply(
        lambda x: (x - x.min()) / (x.max() - x.min()))
    expr = expr.apply(lambda x: (x - x.min()) / (x.max() - x.min()))


def load_patient_expression(base_dir):
    base_path = Path(base_dir)
    expr_dict = dict()
    patient_dirs = {fl.name: fl for fl in base_path.iterdir()
                    if fl.is_dir()}

    for patient, patient_dir in patient_dirs.items():
        out_dir = list((patient_dir / 'output').glob('tatlow_*kallisto'))

        if len(out_dir) == 1:
            for samp_dir in out_dir[0].iterdir():
                expr_fl = list(samp_dir.glob('abundance.tsv'))

                if len(expr_fl) == 1:
                    expr_tbl = pd.read_csv(expr_fl[0].open(), sep='\t')
                    feat_data = expr_tbl['target_id'].str.split('|')

                    expr_dict[patient, samp_dir.name] = {
                        tuple(dt[:2]): tpm
                        for dt, tpm in zip(feat_data,
                                           np.log2(expr_tbl['tpm'] + 0.001))
                        }

    return expr_dict


def load_patient_mutations(base_dir):
    base_path = Path(base_dir)
    mut_dict = dict()

    patient_dirs = {fl.name: fl for fl in base_path.iterdir()
                    if fl.is_dir()}

    for patient, patient_dir in patient_dirs.items():
        out_fls = (patient_dir / 'output' / 'cancer_exome').glob(
            '*SMMART_Cancer_Exome*/*Mutect*.maf')

        for out_fl in out_fls:
            if out_fl.stat().st_size > 0:
                mut_dict[patient, out_fl] = pd.read_csv(
                    out_fl.open('r', encoding='latin_1'), sep='\t',
                    comment='#', low_memory=False
                    )

    return mut_dict

