# -*- coding: utf-8 -*-
"""What kind of request this is, and what has to happen to it.

The type carries what distinguishes one kind of request from another, rather
than a chain of comparisons against a string in code. Whether it goes past the project engineer, whether it
goes past HR, and how it is numbered are three fields on the type, and adding a
type is adding a record.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class ConstructionRequestType(models.Model):
    _name = 'construction.request.type'
    _description = "Request Type"
    _order = 'sequence, id'

    name = fields.Char(string="Name", required=True, translate=True)
    # The short key people use and the sequences are named after: MR, ALR, ASR.
    # It is on the document, so it is not a technical field people never see.
    code = fields.Char(
        string="Code", required=True, index=True,
        help="Short code shown on the request and used in its number: "
             "MR, ALR, ASR, SPC.",
    )
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    image = fields.Image(string="Image", max_width=512, max_height=512)
    description = fields.Text(string="Description", translate=True)

    # ------------------------------------------------------------------
    # the review chain
    # ------------------------------------------------------------------
    # Not every request goes the same way: a material request goes to the
    # project engineer and then to approval, and a leave request goes through
    # HR in between. That is a checkbox on the type.
    needs_pe_review = fields.Boolean(
        string="Project Engineer Review", default=True,
        help="The request waits for the project engineer or project "
             "coordinator before it goes any further.",
    )
    needs_hr_review = fields.Boolean(
        string="HR Review", default=False,
        help="The request waits for HR after the project review and before "
             "final approval. Leave, advance and certificate requests do; "
             "material and payment requests do not.",
    )

    # ------------------------------------------------------------------
    # numbering
    # ------------------------------------------------------------------
    # Whether somebody may raise one of these here, today.
    #
    # Two places accepting the same request is how a number gets issued twice.
    # So a type is opened for new requests one at a time, by ticking this on
    # the type - not by editing a view.
    open_for_new = fields.Boolean(
        string="Can Be Raised Here", default=False,
        help="Tick it when this kind of request is raised in this application. "
             "Until then its New button is hidden and the type cannot be "
             "chosen on a new request; the ones already raised stay readable.",
    )

    numbering = fields.Selection(
        [
            ('global', "One sequence for the type"),
            ('per_project', "A sequence per company and project"),
        ],
        string="Numbering", default='global', required=True,
        help="A leave request is numbered from one sequence for the whole "
             "company. A material request is numbered per project, so each "
             "project's requests run 1, 2, 3 of their own.",
    )
    sequence_id = fields.Many2one(
        'ir.sequence', string="Number Sequence", copy=False,
        help="Used when this type is numbered globally. Left empty, one is "
             "made the first time a request of this type is submitted.",
    )
    sequence_ids = fields.One2many(
        'construction.request.sequence', 'request_type_id', string="Project Sequences",
    )
    sequence_count = fields.Integer(
        string="Number of Project Sequences", compute='_compute_sequence_count',
    )

    _code_unique = models.Constraint(
        'UNIQUE(code)',
        "That request code is already used by another request type.",
    )

    @api.depends('sequence_ids')
    def _compute_sequence_count(self):
        for rec in self:
            rec.sequence_count = len(rec.sequence_ids)

    # ------------------------------------------------------------------
    # how many are waiting
    # ------------------------------------------------------------------
    # Stored counters would have to be refreshed by somebody, and between one
    # refresh and the next the numbers on the screen would be stale.
    #
    # They are counted here instead, in one grouped query for every type at
    # once, and they are never wrong because they are never kept.
    pending_pe_count = fields.Integer(
        string="Waiting for Project Review", compute='_compute_pending',
    )
    pending_hr_count = fields.Integer(
        string="Waiting for HR", compute='_compute_pending',
    )
    pending_approval_count = fields.Integer(
        string="Waiting for Approval", compute='_compute_pending',
    )
    pending_count = fields.Integer(
        string="Waiting", compute='_compute_pending',
        help="Everything of this type that has been submitted and not yet "
             "approved, rejected or cancelled.",
    )

    WAITING = ('pe_review', 'hr_review', 'to_approve')

    def _compute_pending(self):
        counts = {}
        if self.ids:
            for request_type, state, count in self.env['construction.request']._read_group(
                    [('request_type_id', 'in', self.ids),
                     ('state', 'in', list(self.WAITING))],
                    groupby=['request_type_id', 'state'],
                    aggregates=['__count']):
                counts[(request_type.id, state)] = count
        for rec in self:
            rec.pending_pe_count = counts.get((rec.id, 'pe_review'), 0)
            rec.pending_hr_count = counts.get((rec.id, 'hr_review'), 0)
            rec.pending_approval_count = counts.get((rec.id, 'to_approve'), 0)
            rec.pending_count = (rec.pending_pe_count + rec.pending_hr_count
                                 + rec.pending_approval_count)

    def action_new_request(self):
        """Start a request of this kind, from the card that counts them.

        The dashboard is where somebody stands when they realise they need to
        raise one, and sending them to a different menu to pick the type again
        from a dropdown is a step that exists only because nobody put a button
        here.
        """
        self.ensure_one()
        if not self.open_for_new:
            raise UserError(self.env._(
                "%s requests are not raised here yet. They are still made in "
                "the old application; when that changes, tick \"Can Be Raised "
                "Here\" on the type.", self.name))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("New %s", self.name),
            'res_model': 'construction.request',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_request_type_id': self.id},
        }

    def action_open_pending(self):
        """The requests behind one of those numbers.

        A count nobody can click is a number somebody has to go and look for
        by hand.
        """
        self.ensure_one()
        states = self.env.context.get('pending_states') or list(self.WAITING)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("%s waiting", self.display_name),
            'res_model': 'construction.request',
            'domain': [('request_type_id', '=', self.id),
                       ('state', 'in', states)],
            'context': {'default_request_type_id': self.id},
            'view_mode': 'list,form',
        }

    @api.model
    def _for_code(self, code):
        return self.search([('code', '=', code)], limit=1)

    # ------------------------------------------------------------------
    # the number
    # ------------------------------------------------------------------
    def _next_number(self, company=None, project=None):
        """The next request number for this type.

        Globally numbered types draw from their own sequence, made on first
        use. Per-project types are routed to the sequence record for that
        company and project, which is where the prefix lives.
        """
        self.ensure_one()
        if self.numbering == 'per_project':
            line = self.env['construction.request.sequence']._for(self, company, project)
            return line._next()
        if not self.sequence_id:
            self.sequence_id = self.env['ir.sequence'].sudo().create({
                'name': "Request - %s" % (self.name or self.code),
                'code': 'construction.request.%s' % (self.code or self.id),
                'prefix': '%s/' % (self.code or ''),
                'padding': 4,
                'implementation': 'standard',
            })
        return self.sequence_id.sudo().next_by_id()
