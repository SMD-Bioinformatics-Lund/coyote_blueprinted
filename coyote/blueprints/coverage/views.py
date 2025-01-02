"""
Coyote coverage for mane-transcripts
"""

from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory, flash, abort, jsonify
from flask_login import current_user, login_required
from pprint import pformat
from wtforms import BooleanField
from coyote.extensions import store, util
from coyote.blueprints.coverage import cov_bp
from coyote.blueprints.home import home_bp
from coyote.errors.exceptions import AppError
from typing import Literal, Any
from datetime import datetime
from collections import defaultdict
from flask_weasyprint import HTML, render_pdf
from coyote.blueprints.dna.forms import GeneForm
import os

@cov_bp.route("/<string:sample_id>", methods=["GET", "POST"])
@login_required
def get_cov(sample_id):
    cov_cutoff = 500
    if request.method == "POST":
        cov_cutoff_form = request.form.get('depth_cutoff')
        cov_cutoff = int(cov_cutoff_form)
    sample = store.sample_handler.get_sample(sample_id) 
    
    assay: str | None | Literal["unknown"] = util.common.get_assay_from_sample(sample)
    gene_lists, genelists_assay = store.panel_handler.get_assay_panels(assay)
    
    smp_grp = util.common.select_one_sample_group(sample.get("groups"))
    # Get group parameters from the sample group config file
    group_params = util.common.get_group_parameters(smp_grp)

    # Get group defaults from coyote config, if not found in group config
    settings = util.common.get_group_defaults(group_params)
    genelist_filter = sample.get("checked_genelists", settings["default_checked_genelists"])
    filter_genes = util.common.create_filter_genelist(genelist_filter, gene_lists)
    cov_dict = store.coverage2_handler.get_sample_coverage(str(sample['_id']))
    del cov_dict['_id']
    del sample['_id']
    filtered_dict = filter_genes_from_form(cov_dict,filter_genes)
    filtered_dict = find_low_covered_genes(filtered_dict,cov_cutoff,assay)
    filtered_dict = organize_data_for_d3(filtered_dict)
    
    blacklisted = store.coverageassay_handler.get_regions_per_assay(assay)
    return render_template(
        "show_cov.html",
        coverage=filtered_dict,
        cov_cutoff=cov_cutoff,
        sample=sample,
        genelists=genelist_filter,
        assay=assay
    )

@app.route('/update-gene-status', methods=['POST'])
def update_gene_status():
    data = request.get_json()
    gene = data.get('gene')
    status = data.get('status')
    coord = data.get('coord')
    coord = coord.replace(':','_')
    coord = coord.replace('-','_')
    assay = data.get('assay')
    region = data.get('region')
    response = store.coverageassay_handler.blacklist_coord(gene,coord,region,assay)
    # Return a response
    return jsonify({'message': f'Status for gene {gene}:{coord} updated to {status} for assay: {assay}'})

def find_low_covered_genes(cov,cutoff,assay):
    """
    find low covered parts in defined regions of interest
    """
    keep = defaultdict(dict)
    for gene in cov['genes']:
        has_low = False
        if 'CDS' in cov['genes'][gene]:
            has_low = reg_low(cov['genes'][gene]['CDS'],"CDS", cutoff,gene, assay)
        if 'probes' in cov['genes'][gene]:
           has_low = reg_low(cov['genes'][gene]['probes'],"probe", cutoff,gene, assay)
        if has_low == True:
            keep['genes'][gene] = cov['genes'][gene]
    return keep

def organize_data_for_d3(filtered_dict):
    """
    This is for javascript. It's imported as dicts to
    """
    for gene in filtered_dict['genes']: 
        if 'exons' in filtered_dict['genes'][gene]:
            exons = []
            for exon in filtered_dict['genes'][gene]['exons']:
                exons.append(filtered_dict['genes'][gene]['exons'][exon])
            filtered_dict['genes'][gene]['exons'] = exons
        if 'CDS' in filtered_dict['genes'][gene]:
            cds = []
            for exon in filtered_dict['genes'][gene]['CDS']:
                cds.append(filtered_dict['genes'][gene]['CDS'][exon])
            filtered_dict['genes'][gene]['CDS'] = cds
        if 'probes' in filtered_dict['genes'][gene]:
            probes = []
            for probe in filtered_dict['genes'][gene]['probes']:
                probes.append(filtered_dict['genes'][gene]['probes'][probe])
            filtered_dict['genes'][gene]['probes'] = probes

    return filtered_dict

def filter_genes_from_form(cov_dict,filter_genes):
    if len(filter_genes) > 0:
        filtered_dict = defaultdict(dict)
        for gene in cov_dict['genes']:
            if gene in filter_genes:
                filtered_dict['genes'][gene] = cov_dict['genes'][gene]
        return filtered_dict
    else:
        return cov_dict

def reg_low(region_dict, region, cutoff,gene, assay):
    """
    filter against cutoff ignore if region is blacklisted
    """
    has_low = False
    for reg in region_dict:
        if 'cov' in region_dict[reg]:
            if float(region_dict[reg]['cov']) < cutoff:
                blacklisted = store.coverageassay_handler.is_region_blacklisted(gene,region,reg,assay)
                if not blacklisted:
                    has_low = True
    return has_low