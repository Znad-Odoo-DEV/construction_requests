# -*- coding: utf-8 -*-
"""Who approves a request that no project answers for.

The fallback is the company: everything of a company can go to one person,
and a request with no project at all still has to reach somebody. That
fallback is this field.
"""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_request_approver_id = fields.Many2one(
        'res.users', string="Request Approver",
        domain="[('share', '=', False)]",
        help="Who approves requests of this company when the project does not "
             "say, or when there is no project.",
    )
