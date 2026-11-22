# -*- coding: utf-8 -*-
"""The numbering of one request type, on one project, for one company.

The combination is a record, and it owns its ir.sequence: made the first
time it is used, named after the combination, and editable afterwards by anyone
who needs to reset a counter or change a prefix.
"""
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ConstructionRequestSequence(models.Model):
    _name = 'construction.request.sequence'
    _description = "Request Numbering per Project"
    _order = 'company_id, project_id, request_type_id'

    request_type_id = fields.Many2one(
        'construction.request.type', string="Request Type",
        required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, index=True,
        default=lambda self: self.env.company,
    )
    project_id = fields.Many2one(
        'project.project', string="Project", required=True, index=True,
    )
    prefix = fields.Char(
        string="Prefix",
        help="Put in front of the number. Left empty, it is built from the "
             "company code, the project and the request code.",
    )
    sequence_id = fields.Many2one(
        'ir.sequence', string="Sequence", copy=False, readonly=True,
        help="Made the first time this combination numbers a request.",
    )
    next_number = fields.Integer(
        string="Next Number", compute='_compute_next_number',
        inverse='_inverse_next_number',
        help="The number the next request of this kind will get.",
    )
    active = fields.Boolean(string="Active", default=True)

    _one_per_combination = models.Constraint(
        'UNIQUE(request_type_id, company_id, project_id)',
        "That request type is already numbered for this company and project.",
    )

    @api.depends('sequence_id.number_next_actual')
    def _compute_next_number(self):
        for rec in self:
            rec.next_number = rec.sequence_id.number_next_actual or 1

    def _inverse_next_number(self):
        for rec in self:
            if rec.sequence_id:
                rec.sequence_id.sudo().number_next_actual = rec.next_number or 1

    @api.depends('request_type_id', 'company_id', 'project_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s / %s / %s" % (
                rec.company_id.name or '',
                rec.project_id.name or '',
                rec.request_type_id.code or '')

    # ------------------------------------------------------------------
    @api.model
    def _for(self, request_type, company, project):
        """The numbering record for one combination, made if it is not there.

        Made rather than refused: a new project should not stop somebody
        submitting a request, and a numbering row with a sensible default
        prefix is not a decision anybody needs to be asked about. What it is
        called can be changed afterwards; what matters is that the request gets
        a number and nobody is blocked at five in the afternoon.
        """
        if not request_type:
            raise UserError(_("This request has no type, so it cannot be numbered."))
        if not project:
            raise UserError(_(
                "%s requests are numbered per project, and this one names no "
                "project.", request_type.display_name))
        company = company or self.env.company
        found = self.search([
            ('request_type_id', '=', request_type.id),
            ('company_id', '=', company.id),
            ('project_id', '=', project.id),
        ], limit=1)
        if found:
            return found
        return self.sudo().create({
            'request_type_id': request_type.id,
            'company_id': company.id,
            'project_id': project.id,
        })

    def _default_prefix(self):
        """COMPANY/PROJECT/TYPE/ - for example ABC/PRJ/MR/.

        The company's short code can live on construction_payroll, which this
        module does not depend on and should not: requests are not payroll. So
        it is read if it is there, and otherwise a short code is taken from the
        company name, rather than dragging in a dependency for one string.
        """
        self.ensure_one()
        company = self.company_id
        code = (company.construction_company_code
                if 'construction_company_code' in company._fields else False)
        parts = [
            code or re.sub(r'[^A-Za-z0-9]', '', company.name or '')[:3].upper(),
            self.project_id.name or '',
            self.request_type_id.code or '',
        ]
        return "/".join(part for part in parts if part) + "/"

    def _next(self):
        """The next number for this combination."""
        self.ensure_one()
        if not self.sequence_id:
            self.sudo().sequence_id = self.env['ir.sequence'].sudo().create({
                'name': self.display_name,
                'code': 'construction.request.%s.%s.%s' % (
                    self.request_type_id.code or self.request_type_id.id,
                    self.company_id.id, self.project_id.id),
                'prefix': self.prefix or self._default_prefix(),
                'padding': 3,
                'implementation': 'standard',
                'company_id': self.company_id.id,
            })
        elif self.prefix and self.sequence_id.prefix != self.prefix:
            # The prefix is edited here, on the record people can see, and the
            # sequence follows it. Two places holding the same string and
            # disagreeing is how a month of documents comes out named wrongly.
            self.sequence_id.sudo().prefix = self.prefix
        return self.sequence_id.sudo().next_by_id()
