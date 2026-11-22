# -*- coding: utf-8 -*-
"""Who approves requests raised on this project, and who a certificate goes to.

The approver is a field on the project, which is where it is a fact about:
a new project, a promotion or somebody leaving is a field somebody edits
rather than code somebody deploys.

The consultant's addresses are the same shape of thing. They are filled on
payment certificates, because a certificate is what gets sent to the
consultant for approval. They are a fact about a project - which consultant is
on it and where their site engineer and resident engineer read their mail -
rather than a company-wide setting, since different projects can have
different consultants.
"""
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_request_approver_id = fields.Many2one(
        'res.users', string="Request Approver",
        domain="[('share', '=', False)]",
        help="Who approves requests raised on this project. Left empty, the "
             "company's approver is used.",
    )
    construction_consultant_email = fields.Char(
        string="Consultant (Site)",
        help="Where a payment certificate is sent for the consultant's site "
             "engineer to approve.",
    )
    construction_consultant_re_email = fields.Char(
        string="Consultant (Resident Engineer)",
        help="The resident engineer's address, when the consultant has one.",
    )
