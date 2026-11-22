# -*- coding: utf-8 -*-
"""What a request is made of: materials, or installments.

There are separate line models, each with the fields its own kind of request
has and no others, so a quantity never means a number of bags on one and a sum
of money on another.

On the material line there is one of each quantity, and the two that can be
worked out are worked out.
"""
from odoo import api, fields, models


class ConstructionRequestMaterialLine(models.Model):
    _name = 'construction.request.material.line'
    _description = "Requested Material"
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one(
        'construction.request', string="Request", required=True,
        ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    project_id = fields.Many2one(related='request_id.project_id', store=True, index=True)
    state = fields.Selection(related='request_id.state', store=True, index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    item_no = fields.Integer(string="Item No.")

    # product.product rather than product.template: a line is a thing you can
    # count in a warehouse, and quantity on hand is a variant's number.
    product_id = fields.Many2one(
        'product.product', string="Material", required=True, index=True,
        domain="[('type', 'in', ('consu', 'product'))]",
    )
    description = fields.Char(string="Description")
    uom_id = fields.Many2one(related='product_id.uom_id', string="Unit")
    quantity = fields.Float(
        string="Quantity Required", required=True, default=1.0,
        digits='Product Unit of Measure',
    )

    # Worked out rather than typed, because both of them are already known:
    # what was asked for before is in the other requests, and what is in stock
    # is in the stock. Typed, they are right on the day and wrong afterwards.
    quantity_previous = fields.Float(
        string="Previously Requested", compute='_compute_quantity_previous',
        digits='Product Unit of Measure',
        help="The same material on other requests for this project that have "
             "been submitted and not rejected. This request is not counted.",
    )
    quantity_available = fields.Float(
        string="In Stock", compute='_compute_quantity_available',
        digits='Product Unit of Measure',
        help="What the company holds of this material now.",
    )

    # Typed, and staying typed.
    #
    # A bill item is WORK - "supply and lay 200mm blockwork", priced by the
    # square metre. A material requirement is a THING - four hundred bags of
    # cement. They are not the same list and one does not derive the other.
    #
    # So there is nothing to compute them from, and a number somebody types is
    # more honest than one derived from a list of a different kind of thing.
    quantity_project = fields.Float(
        string="Project Quantity", digits='Product Unit of Measure',
        help="What the project is allowed of this material in total, if "
             "anybody has worked it out. Left empty it is simply not known, "
             "and the balance below says nothing rather than guessing.",
    )
    quantity_sector = fields.Float(
        string="Sector Quantity", digits='Product Unit of Measure',
        help="The same, for one part of the job.",
    )
    balance_to_order = fields.Float(
        string="Balance to Order", compute='_compute_balance',
        digits='Product Unit of Measure',
        help="Project quantity, less what has been requested before, less this "
             "request. It is nought while the project quantity is unknown, "
             "because a balance against nothing is not a balance.",
    )
    has_balance = fields.Boolean(
        string="Balance Is Known", compute='_compute_balance',
        help="There is a project quantity to measure the balance against.",
    )

    @api.depends('product_id', 'project_id', 'request_id')
    def _compute_quantity_previous(self):
        for line in self:
            if not line.product_id or not line.project_id:
                line.quantity_previous = 0.0
                continue
            others = self.search([
                ('product_id', '=', line.product_id.id),
                ('project_id', '=', line.project_id.id),
                ('state', 'not in', ('draft', 'rejected', 'cancelled')),
                ('id', '!=', line._origin.id or 0),
            ])
            line.quantity_previous = sum(others.mapped('quantity'))

    @api.depends('product_id', 'company_id')
    def _compute_quantity_available(self):
        for line in self:
            product = line.product_id
            if not product:
                line.quantity_available = 0.0
                continue
            line.quantity_available = product.with_company(
                line.company_id or self.env.company).qty_available

    @api.depends('quantity', 'quantity_previous', 'quantity_project')
    def _compute_balance(self):
        """Nothing, while nobody has said what the project is allowed.

        Subtracting from a project quantity of nought gives a large negative
        number on ninety-seven per cent of lines, and a column that reads
        minus five hundred on every screen is worse than an empty one: somebody
        eventually believes it.
        """
        for line in self:
            line.has_balance = bool(line.quantity_project)
            line.balance_to_order = (
                line.quantity_project - line.quantity_previous - line.quantity
                if line.quantity_project else 0.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id and not line.description:
                line.description = line.product_id.display_name


class ConstructionRequestInstallment(models.Model):
    _name = 'construction.request.installment'
    _description = "Advance Repayment Installment"
    _order = 'request_id, due_date, id'

    request_id = fields.Many2one(
        'construction.request', string="Request", required=True,
        ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='request_id.currency_id')
    name = fields.Char(string="Installment", required=True)
    # A date rather than a month and a year in two selection fields, which
    # sort badly as text and cannot be compared to a payslip period without
    # being taken apart first.
    due_date = fields.Date(
        string="Due", required=True,
        help="The month this installment is deducted in. Held as the first of "
             "the month.",
    )
    amount = fields.Monetary(string="Amount", required=True)

    @api.depends('name', 'due_date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s (%s)" % (
                rec.name or '', rec.due_date and rec.due_date.strftime('%b %Y') or '')
