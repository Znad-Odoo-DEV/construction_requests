# -*- coding: utf-8 -*-
"""A request: raised by somebody, reviewed by the people its type asks for, approved.

Design notes:

  One status field, read by reports and rules alike.

  Cancelling is a state, not a deletion: the request, its chatter and its
  history stay, and the number it had is never used again.

  Which review a request goes through is on its type, so the same three
  buttons serve all thirteen kinds and adding a fourteenth is adding a record.

  What the employee knows (nationality, passport, company) is read from the
  employee, not copied onto the request.
"""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class ConstructionRequest(models.Model):
    _name = 'construction.request'
    _description = "Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc, id desc'

    # Binary fields whose file should also appear in the chatter.
    #
    # Odoo already stores a Binary as an ir.attachment, but that one carries
    # res_field, which makes it internal storage: it does not show in the
    # chatter, cannot be attached to an email, and cannot be found by anybody
    # who does not already know which field to open.
    #
    # A button that makes a second, visible attachment would have to be
    # pressed by somebody, and a file uploaded without a press would be a file
    # nobody could find. Here the copy is made when the field is written,
    # which is the moment it is wanted.
    #
    # A method rather than a class attribute, because two bridges each set an
    # attribute and the second one wins - the payroll bridge's two documents
    # would have replaced the subcontract bridge's tax invoice, or the other
    # way round depending on load order, and nothing would have said so. A
    # super() call adds.
    _rec_names_search = ['name', 'description']

    # ------------------------------------------------------------------
    # identity
    # ------------------------------------------------------------------
    # Empty until it is submitted, rather than the usual '/'. The number is
    # unique per company and Postgres does not collide two NULLs, so an empty
    # name lets a hundred drafts exist at once and still guarantees that no two
    # submitted requests share a number. A default of '/' would have made the
    # second draft in the database impossible - which is how this was found.
    name = fields.Char(
        string="Number", copy=False, readonly=True, index=True, tracking=True,
        help="Given when the request is submitted, from the numbering its type "
             "uses. A draft has none, which is how you can tell one.",
    )
    reference = fields.Char(
        string="Base Number", copy=False, readonly=True,
        help="The number without the revision suffix.",
    )
    revision = fields.Integer(
        string="Revision", default=0, copy=False, readonly=True, tracking=True,
        help="How many times this request has been sent back and resubmitted. "
             "The number becomes NUMBER-R1, -R2 and so on.",
    )
    # Written by the record, not by the person raising it.
    #
    # A typed name would repeat what is already on the record: the number, the
    # type, the person. Typing it again is how one request says "Annual Leave
    # Request" and the next says "annual leave" and neither can be searched for
    # reliably.
    #
    # Computed and stored and NOT readonly, which is Odoo's way of saying "we
    # will fill this in, and you may still say something else". A material
    # request for a particular pour wants "Cement for the raft" on it, and the
    # moment somebody types that the compute stops fighting them.
    description = fields.Char(
        string="Subject", required=True, tracking=True,
        compute='_compute_description', store=True, readonly=False,
        # precompute, or the NOT NULL that "required" puts on the column fires
        # before the compute has run - Odoo works out stored computes after the
        # INSERT unless it is told to do it first. This is the same declaration
        # sale.order.line.name carries, for the same reason.
        precompute=True,
        help="Filled in from the type and who it is for. Type over it when "
             "the request is about something in particular.",
    )

    def _suggested_description(self):
        """What this request would be called if nobody said otherwise."""
        self.ensure_one()
        if not self.request_type_id:
            return self.env._("Request")
        # The person for an HR request, the project for a site one - which is
        # what tells two of them apart in a list of fifty.
        about = self.employee_id.name or self.project_id.display_name or ''
        return ("%s - %s" % (self.request_type_id.name, about) if about
                else self.request_type_id.name)

    @api.depends('request_type_id', 'employee_id', 'project_id')
    def _compute_description(self):
        """Update it, unless somebody has written their own.

        A stored computed field that is editable gets recomputed whenever one
        of its dependencies moves, and that discards what a person typed. The
        first version did exactly that: type "Cement for the raft", then set
        the employee, and the raft was gone.

        So it only writes where the current value is one this method could
        have produced - empty, or the type's name with or without a name after
        it. Anything else is somebody's sentence and is left alone.

        The limit, said out loud: a person who types the exact words the
        suggestion would have used gets their line updated later. They lose
        nothing, because it is the same line.
        """
        for rec in self:
            current = (rec.description or '').strip()
            type_name = rec.request_type_id.name or ''
            ours = (not current
                    or not type_name
                    or current == type_name
                    or current.startswith("%s - " % type_name))
            if ours:
                rec.description = rec._suggested_description()
            else:
                # Assign it back to itself: a compute must set every record it
                # is called for, or Odoo raises about a field it did not fill.
                rec.description = current

    request_type_id = fields.Many2one(
        'construction.request.type', string="Type", required=True, tracking=True,
        index=True, ondelete='restrict',
        # Only the kinds this application accepts today, plus whatever this
        # record already is, so a request keeps its type and stays readable
        # even after that kind is closed for new requests.
        domain="['|', ('id', '=', request_type_id), ('open_for_new', '=', True)]",
    )
    type_code = fields.Char(related='request_type_id.code', string="Type Code", store=True)
    needs_pe_review = fields.Boolean(related='request_type_id.needs_pe_review')
    needs_hr_review = fields.Boolean(related='request_type_id.needs_hr_review')
    numbering = fields.Selection(related='request_type_id.numbering')

    company_id = fields.Many2one(
        'res.company', string="Company", required=True, index=True,
        default=lambda self: self.env.company,
    )
    project_id = fields.Many2one(
        'project.project', string="Project", index=True, tracking=True,
        domain="[('company_id', 'in', (False, company_id))]",
    )
    employee_id = fields.Many2one(
        'hr.employee', string="Requested For", index=True, tracking=True,
        help="The person the request is about. A material request has none.",
    )
    # The face beside the name, so whoever reviews or pays an advance sees who
    # it is for. Read off the employee rather than copied: the request shows
    # the photo the employee file holds today.
    employee_image = fields.Image(
        related='employee_id.image_256', string="Employee Photo")
    # Filled when the record is made, not when it is submitted. The record rule
    # for a requester is "the ones you raised", and a rule is checked on create
    # - so setting this at submit meant a requester could not create a request
    # at all. They wrote a draft, the rule looked for their name on it, found
    # an empty field and refused the row they had just written. Only reviewers
    # and approvers, who see everything, could raise anything.
    requested_by_id = fields.Many2one(
        'res.users', string="Submitted By", copy=False, readonly=True,
        tracking=True, default=lambda self: self.env.user,
    )
    date_request = fields.Datetime(
        string="Submitted On", copy=False, readonly=True, tracking=True,
    )
    active = fields.Boolean(string="Active", default=True)
    # The colour somebody puts on a card themselves. It is here because the
    # kanban's highlight needs a field to read, and it costs one integer
    # column.
    color = fields.Integer(string="Colour Index", default=0)

    # ------------------------------------------------------------------
    # the one state
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ('draft', "Draft"),
            ('pe_review', "Project Review"),
            ('hr_review', "HR Review"),
            ('to_approve', "To Approve"),
            ('approved', "Approved"),
            ('rejected', "Rejected"),
            ('cancelled', "Cancelled"),
        ],
        string="Status", default='draft', required=True,
        tracking=True, index=True, copy=False,
        # Every column, always, even when empty. A kanban grouped by state is
        # a picture of the workflow, and a workflow with a step missing
        # because nothing is sitting in it today is a picture that changes
        # shape every morning - and one nobody can drop a card into.
        group_expand='_group_expand_state',
    )

    @api.model
    def _group_expand_state(self, states, domain):
        return [key for key, _label in type(self).state.selection]

    pe_reviewer_id = fields.Many2one('res.users', string="Project Reviewer",
                                     copy=False, readonly=True)
    pe_review_date = fields.Datetime(string="Project Review Date",
                                     copy=False, readonly=True)
    hr_reviewer_id = fields.Many2one('res.users', string="HR Reviewer",
                                     copy=False, readonly=True)
    hr_review_date = fields.Datetime(string="HR Review Date",
                                     copy=False, readonly=True)
    # Who SHOULD approve it, which is not who did. The gap between the two is
    # the whole reason to keep them apart: work gets approved by whoever is
    # at their desk, and knowing whose it was is what makes that visible.
    approver_expected_id = fields.Many2one(
        'res.users', string="To Be Approved By",
        compute='_compute_approver_expected', store=True, readonly=False,
        tracking=True, domain="[('share', '=', False)]",
        help="Read from the project, or from the company when the project "
             "does not say. Overridable on one request without changing "
             "either.",
    )
    approver_id = fields.Many2one('res.users', string="Approved By",
                                  copy=False, readonly=True, tracking=True)
    approval_date = fields.Datetime(string="Approval Date",
                                    copy=False, readonly=True, tracking=True)
    rejected_by_id = fields.Many2one('res.users', string="Rejected By",
                                     copy=False, readonly=True)
    rejection_reason = fields.Text(string="Reason", copy=False, tracking=True)
    # Why it went back a step. Without a reason the person picking it up has
    # to guess what was wrong with it or ask the person who sent it.
    return_note = fields.Text(
        string="Sent Back Because", copy=False,
        help="What has to change before this goes forward again.",
    )

    notes = fields.Text(string="Notes")

    # ------------------------------------------------------------------
    # what is being asked for
    # ------------------------------------------------------------------
    currency_id = fields.Many2one(
        related='company_id.currency_id', string="Currency", store=True,
    )
    amount = fields.Monetary(
        string="Amount", tracking=True,
        help="The sum asked for. An advance, a payment certificate.",
    )
    installment_count = fields.Integer(
        string="Installments", default=1,
        help="How many months an advance is repaid over.",
    )
    material_line_ids = fields.One2many(
        'construction.request.material.line', 'request_id', string="Materials",
        copy=True,
    )
    # When the material is wanted on site: a material request that does not
    # say when is one the store cannot put in order against the others.
    #
    # A date, and empty means as soon as possible. Sites do want to say "as
    # soon as possible", and a date field they must fill would be answered
    # with today's date and mean nothing.
    #
    # Empty is therefore a real value here rather than a missing one, and it is
    # the common one. The form says so and the printed page says ASAP, which is
    # the word the store has been reading for two years.
    date_required = fields.Date(
        string="Needed By", tracking=True,
        help="When the material is wanted on site. Leave it empty for as soon "
             "as possible, which is what most requests mean.",
    )
    date_required_label = fields.Char(
        string="Needed", compute='_compute_date_required_label',
        help="The date, or the word the store has always read when there is "
             "none.",
    )

    @api.depends('date_required')
    def _compute_date_required_label(self):
        for rec in self:
            rec.date_required_label = (
                fields.Date.to_string(rec.date_required)
                if rec.date_required else "ASAP")
    installment_ids = fields.One2many(
        'construction.request.installment', 'request_id', string="Repayment",
        copy=True,
    )
    installment_total = fields.Monetary(
        string="Scheduled", compute='_compute_installment_total',
        help="What the installments add up to. It should be the amount asked "
             "for, and the form says so when it is not.",
    )
    # Every printed page that carries an amount carries it spelled out
    # underneath. It is computed rather than typed by hand, so a spelling
    # mistake cannot be on file twice. Computed here, and only once: a bridge that spells a different number says which one by
    # overriding _amount_to_spell, not by declaring the field again. Two
    # modules both declaring amount_in_words on construction.request would have meant
    # whichever loaded last silently decided what every page printed.
    amount_in_words = fields.Char(
        string="In Words", compute='_compute_amount_in_words',
        help="The amount, spelled. Computed, not stored: a column holding the "
             "spelling of another column disagrees with it eventually.",
    )

    def _amount_to_spell(self):
        """Which number this kind of request prints in words."""
        self.ensure_one()
        return self.amount

    @api.depends('amount', 'currency_id')
    def _compute_amount_in_words(self):
        for rec in self:
            value = rec._amount_to_spell()
            rec.amount_in_words = (
                rec.currency_id.amount_to_text(value)
                if rec.currency_id and value else '')

    @api.depends('installment_ids.amount')
    def _compute_installment_total(self):
        for rec in self:
            rec.installment_total = sum(rec.installment_ids.mapped('amount'))

    def action_generate_installments(self):
        """Split the amount over the months, starting next month.

        A date does the month arithmetic, and the last installment absorbs the rounding so the
        installments add up to the amount rather than to a cent less.
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(self.env._(
                    "%s has been submitted; its repayment cannot be rebuilt.",
                    rec.display_name))
            if not rec.amount or rec.installment_count < 1:
                raise UserError(self.env._(
                    "Set the amount and the number of installments first."))
            rec.installment_ids.unlink()
            start = fields.Date.context_today(rec).replace(day=1) + relativedelta(months=1)
            base = round(rec.amount / rec.installment_count, 2)
            allocated, lines = 0.0, []
            for index in range(1, rec.installment_count + 1):
                last = index == rec.installment_count
                value = round(rec.amount - allocated, 2) if last else base
                allocated += value
                lines.append((0, 0, {
                    'name': self.env._("Installment no.%02d") % index,
                    'due_date': start + relativedelta(months=index - 1),
                    'amount': value,
                }))
            rec.installment_ids = lines
        return True

    _reference_company_unique = models.Constraint(
        'UNIQUE(name, company_id)',
        "That request number already exists in this company.",
    )

    # ------------------------------------------------------------------
    # display
    # ------------------------------------------------------------------
    @api.depends('name', 'description')
    def _compute_display_name(self):
        for rec in self:
            if rec.name:
                rec.display_name = "%s - %s" % (rec.name, rec.description or '')
            else:
                rec.display_name = rec.description or self.env._("New Request")

    # ------------------------------------------------------------------
    # the chain
    # ------------------------------------------------------------------
    @api.depends('project_id.construction_request_approver_id',
                 'company_id.construction_request_approver_id')
    def _compute_approver_expected(self):
        """The project's approver, or the company's when the project is silent.

        This asks the project, which is where the fact lives, and falls back to
        the company.
        """
        for rec in self:
            rec.approver_expected_id = (
                rec.project_id.construction_request_approver_id
                or rec.company_id.construction_request_approver_id)

    # ------------------------------------------------------------------
    # files people upload
    # ------------------------------------------------------------------
    def write(self, vals):
        result = super().write(vals)
        visible = self._visible_files()
        uploaded = [name for name in visible if name in vals and vals[name]]
        if uploaded:
            for rec in self:
                rec._publish_files(uploaded)
        # On the state itself, not on each action. The first version hung this
        # off _post_step, which only three of the seven transitions call - so
        # approving and rejecting left the reviewer's task open on a record
        # that no longer needed them. A rule about what the state means belongs
        # where the state changes.
        if 'state' in vals:
            self._sync_review_activity()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        visible = self._visible_files()
        for rec, vals in zip(records, vals_list):
            uploaded = [name for name in visible if vals.get(name)]
            if uploaded:
                rec._publish_files(uploaded)
        return records

    def _visible_files(self):
        """Binary fields whose file should also show in the chatter.

        Nothing in the base module has one. Each bridge adds its own on top of
        what it was given.
        """
        return ()

    def _publish_files(self, field_names):
        """Put an uploaded file in the chatter, where it can be found.

        One message per upload rather than a silent attachment, because the
        chatter is also the record of when a document arrived and who sent it,
        and that is asked about a signed resignation notice more often than the
        file itself is.
        """
        self.ensure_one()
        for name in field_names:
            data = self[name]
            if not data:
                continue
            field = self._fields[name]
            filename = (self[name + '_filename']
                        if name + '_filename' in self._fields else None)
            filename = filename or "%s.pdf" % (field.string or name)
            already = self.env['ir.attachment'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('res_field', '=', False),
                ('name', '=', filename),
            ], limit=1)
            if already:
                continue
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'datas': data,
                'res_model': self._name,
                'res_id': self.id,
            })
            self.message_post(
                body=self.env._("%s uploaded.", field.string or name),
                attachment_ids=attachment.ids,
            )

    def _first_step(self):
        """Where a request goes when it is submitted."""
        self.ensure_one()
        if self.request_type_id.needs_pe_review:
            return 'pe_review'
        if self.request_type_id.needs_hr_review:
            return 'hr_review'
        return 'to_approve'

    def _step_after_pe(self):
        self.ensure_one()
        return 'hr_review' if self.request_type_id.needs_hr_review else 'to_approve'

    def _step_before(self):
        """The step this request came from, or draft if it came from nowhere.

        Built from the same two questions the forward chain asks rather than
        from a list written backwards - a type that stops needing an HR review
        would otherwise send requests back to a step it no longer has.
        """
        self.ensure_one()
        if self.state == 'to_approve':
            if self.request_type_id.needs_hr_review:
                return 'hr_review'
            if self.request_type_id.needs_pe_review:
                return 'pe_review'
            return 'draft'
        if self.state == 'hr_review':
            return 'pe_review' if self.request_type_id.needs_pe_review else 'draft'
        if self.state == 'pe_review':
            return 'draft'
        return False

    def _check_group(self, group_xmlid, what):
        """Refuse a step to somebody who is not the person for it.

        Hiding the button is not the same as refusing the action. The check is
        here so that the answer is the
        same whether it is reached from the form, from a list, or from a script.
        """
        if not self.env.user.has_group(group_xmlid):
            raise AccessError(self.env._(
                "You are not allowed to %s. That is done by the "
                "%s group.", what,
                self.env.ref(group_xmlid).sudo().name))

    # ------------------------------------------------------------------
    # buttons
    # ------------------------------------------------------------------
    def action_submit(self):
        """Number the request and send it to the first review its type wants."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(self.env._(
                    "%s has already been submitted.", rec.display_name))
            if rec.numbering == 'per_project' and not rec.project_id:
                raise UserError(self.env._(
                    "%s requests are numbered per project. Choose the project "
                    "before submitting.", rec.request_type_id.display_name))
            if not rec.reference:
                rec.reference = rec.request_type_id._next_number(
                    rec.company_id, rec.project_id)
            rec.write({
                'name': rec._numbered_name(),
                # kept, not overwritten: a manager submitting somebody's draft
                # does not become the person who raised it
                'requested_by_id': rec.requested_by_id.id or self.env.user.id,
                'date_request': fields.Datetime.now(),
                'state': rec._first_step(),
            })
            rec._post_step(self.env._(
                "Submitted as %(number)s and waiting for %(who)s.",
                number=rec.name,
                who=dict(rec._fields['state'].selection)[rec.state]))
        return True

    def _numbered_name(self):
        self.ensure_one()
        if self.revision:
            return "%s-R%s" % (self.reference, self.revision)
        return self.reference

    def action_pe_review(self):
        """The project engineer or coordinator has seen it."""
        self._check_group('construction_requests.group_request_pe_review',
                          self.env._("pass a project review"))
        for rec in self:
            if rec.state != 'pe_review':
                raise UserError(self.env._(
                    "%s is not waiting for a project review.", rec.display_name))
            rec.write({
                'pe_reviewer_id': self.env.user.id,
                'pe_review_date': fields.Datetime.now(),
                'state': rec._step_after_pe(),
            })
            rec._post_step(self.env._(
                "Project review passed. Now with %s.",
                dict(rec._fields['state'].selection)[rec.state]))
        return True

    def action_hr_review(self):
        """HR has seen it."""
        self._check_group('construction_requests.group_request_hr_review',
                          self.env._("pass an HR review"))
        for rec in self:
            if rec.state != 'hr_review':
                raise UserError(self.env._(
                    "%s is not waiting for HR.", rec.display_name))
            rec.write({
                'hr_reviewer_id': self.env.user.id,
                'hr_review_date': fields.Datetime.now(),
                'state': 'to_approve',
            })
        return True

    def action_approve(self):
        """Approve it, and let whatever the type produces happen."""
        self._check_group('construction_requests.group_request_approver',
                          self.env._("approve a request"))
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(self.env._(
                    "%s is not waiting for approval.", rec.display_name))
            expected = rec.approver_expected_id
            rec.write({
                'approver_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
                'state': 'approved',
            })
            # Not refused - work gets approved by whoever is at their desk, and
            # a system that stops that stops the job. But it is written down,
            # because "who signed this" is asked months later and the answer
            # has to be somewhere other than somebody's memory.
            if expected and expected != self.env.user:
                rec._post_step(self.env._(
                    "Approved by %(who)s. It was assigned to %(assigned)s.",
                    who=self.env.user.name, assigned=expected.name))
            rec._on_approved()
        return True

    def action_open_related(self):
        """The other requests on this project, or for this person.

        The question somebody has open a request to answer is usually about
        another one: has this material been asked for already, has this
        employee had an advance this year. It is a search, not a stored copy.
        """
        self.ensure_one()
        domain = [('id', '!=', self.id)]
        if self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))
        elif self.project_id:
            domain.append(('project_id', '=', self.project_id.id))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Related Requests"),
            'res_model': 'construction.request',
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'context': {'search_default_group_by_type': 1},
        }

    def _post_step(self, message):
        """One line in the chatter saying what happened and who is next.

        The status change is tracked already, but tracking says a field went
        from one value to another. It does not say that the request is now
        sitting with HR, which is the thing somebody reading the record wants
        to know.
        """
        for rec in self:
            rec.message_post(body=message)

    # ------------------------------------------------------------------
    # telling the person who is being waited on
    # ------------------------------------------------------------------
    # A To-Do activity is raised when a request reaches a reviewer and closed
    # when they act - with a follower alongside. That is how somebody knows
    # they have work; a counter on a dashboard says how
    # many are waiting, not who is being waited on.
    #
    # The followers there were two people written into the rule by name. That
    # is the same fault as the approver map, and it fails the same way: the day
    # one of them leaves, the reminders keep going to them and nobody notices
    # because a request nobody was told about looks exactly like a request
    # nobody has got to yet.
    #
    # So the responsible person is looked up, per step:
    #
    #   project review  the project's manager - project.project.user_id, which
    #                   Odoo already has and the office already maintains, so
    #                   there is no new field to keep up to date
    #   HR review       everyone who can do an HR review in this company. HR is
    #                   a small central team, not a per-project role
    #   to approve      approver_expected_id, which is the project's approver
    #                   falling back to the company's
    WAITING_STATES = ('pe_review', 'hr_review', 'to_approve')

    def _reviewers_for_state(self):
        """Who is being waited on, right now, on this request."""
        self.ensure_one()
        if self.state == 'pe_review':
            return self.project_id.user_id
        if self.state == 'hr_review':
            group = self.env.ref('construction_requests.group_request_hr_review',
                                 raise_if_not_found=False)
            if not group:
                return self.env['res.users']
            # all_user_ids, not user_ids: the first is everyone in the group
            # INCLUDING those who have it through another group they hold, and
            # a manager whose role implies HR review is somebody HR review can
            # wait on. (res.groups.users was removed in 19; user_ids is the
            # explicit members only.)
            return group.sudo().all_user_ids.filtered(
                lambda user: not user.share
                and (not self.company_id or self.company_id in user.company_ids))
        if self.state == 'to_approve':
            return self.approver_expected_id
        return self.env['res.users']

    def _sync_review_activity(self):
        """Close what was open, then open one for whoever is next.

        Closing first, and unconditionally, is what keeps this honest when a
        request moves twice in a day or goes back a step: an activity that
        outlives the state it was raised for is worse than none, because it
        sends somebody to a record that no longer needs them.
        """
        for rec in self:
            rec.activity_feedback(['mail.mail_activity_data_todo'])
            if rec.state not in rec.WAITING_STATES:
                continue
            reviewers = rec._reviewers_for_state()
            if not reviewers:
                # Said out loud rather than passed over. A request waiting on
                # nobody is a request that waits for ever, and the chatter is
                # where somebody looking at it will find out why.
                rec.message_post(body=self.env._(
                    "Nobody is set to handle %(step)s on this request, so no "
                    "reminder was raised. Set the project's manager or "
                    "approver.",
                    step=dict(rec._fields['state'].selection)[rec.state]))
                continue
            step = dict(rec._fields['state'].selection)[rec.state]
            for reviewer in reviewers:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=reviewer.id,
                    summary=self.env._("%(step)s: %(request)s",
                                       step=step, request=rec.name or ''),
                    note=self.env._("%(description)s", description=rec.description or ''),
                )
            # A follower gets the chatter as it happens.
            rec.message_subscribe(
                partner_ids=reviewers.partner_id.ids)

    def _on_approved(self):
        """What an approved request produces.

        Nothing here, on purpose. An approved leave request makes a leave
        allowance and an approved advance request makes an advance, and both of
        those belong to the modules that own those records rather than to this
        one. They hook in here.
        """
        return True

    def action_reject(self):
        """Reject it, and say why.

        The reason is required. A rejection without one sends the requester
        back to the person who rejected it to ask, which is a conversation that
        did not need to happen and usually happens two days later.
        """
        for rec in self:
            if rec.state in ('approved', 'cancelled'):
                raise UserError(self.env._(
                    "%s cannot be rejected now.", rec.display_name))
            if not rec.rejection_reason:
                raise UserError(self.env._(
                    "Say why %s is rejected. The reason is what the requester "
                    "acts on.", rec.display_name))
            rec.write({
                'rejected_by_id': self.env.user.id,
                'state': 'rejected',
            })
        return True

    def action_revise(self):
        """Send it back to be corrected and resubmitted.

        The number is kept and the revision goes up, which is what the site
        expects: ABC/PRJ/MR/007-R1 is the same request as ABC/PRJ/MR/007, seen
        again. A new number would make it look like a second request.
        """
        for rec in self:
            if rec.state in ('draft', 'approved'):
                raise UserError(self.env._(
                    "%s cannot be revised from here.", rec.display_name))
            rec.write({
                'revision': rec.revision + 1,
                'name': "%s-R%s" % (rec.reference, rec.revision + 1),
                'state': 'draft',
                'pe_reviewer_id': False, 'pe_review_date': False,
                'hr_reviewer_id': False, 'hr_review_date': False,
                'approver_id': False, 'approval_date': False,
                'rejected_by_id': False,
            })
        return True

    def action_send_back(self):
        """Back one step, to the reviewer before this one.

        Not the same as revising. Revising sends the whole request to the
        requester with a new revision number, because what is wrong with it is
        theirs to fix. Sending back returns it to the previous REVIEWER, keeps
        the number and the revision, and is what "Send back to HR"
        does - from waiting for approval, back to HR.

        The reason is required, so whoever picks it up knows what was wrong.

        The step is worked out from the type, not from a list written
        backwards, so a type that stops needing an HR review does not send
        requests back to a step it no longer has.
        """
        for rec in self:
            target = rec._step_before()
            if not target:
                raise UserError(self.env._(
                    "%s is not with a reviewer, so there is nobody to send it "
                    "back to.", rec.display_name))
            if not (rec.return_note or '').strip():
                raise UserError(self.env._(
                    "Say what has to change before sending %s back. Whoever "
                    "picks it up reads that and nothing else.",
                    rec.display_name))
            # The review that is being undone is cleared with it: a request
            # sitting at HR again while still carrying the HR reviewer's name
            # and date says it was reviewed when it is waiting to be.
            undo = {'state': target}
            if rec.state == 'to_approve' and target == 'hr_review':
                undo.update(hr_reviewer_id=False, hr_review_date=False)
            elif target == 'pe_review':
                undo.update(pe_reviewer_id=False, pe_review_date=False)
            rec.write(undo)
            rec._post_step(self.env._(
                "Sent back to %(step)s by %(who)s: %(why)s",
                step=dict(rec._fields['state'].selection)[target],
                who=self.env.user.name, why=rec.return_note))
        return True

    def action_cancel(self):
        """Cancel it. Which is a state, and not a deletion."""
        for rec in self:
            if rec.state == 'approved' and not rec._reverse_what_it_produced():
                raise UserError(self.env._(
                    "%s is approved. Approved requests are not cancelled; "
                    "reverse what it produced instead.", rec.display_name))
            rec.state = 'cancelled'
        return True

    def _reverse_what_it_produced(self):
        """Undo what approving this request made, when that can be done
        safely, and say so by returning True. Nothing here knows how; the
        modules that produce something from a request do."""
        self.ensure_one()
        return False

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(self.env._(
                    "%s is approved and cannot go back to draft.",
                    rec.display_name))
            rec.state = 'draft'
        return True

    # ------------------------------------------------------------------
    # guards
    # ------------------------------------------------------------------
    @api.ondelete(at_uninstall=False)
    def _refuse_to_delete_a_submitted_request(self):
        """A submitted request has a number, and a number that disappears is a
        gap somebody will spend an afternoon looking for."""
        submitted = self.filtered(lambda r: r.state != 'draft')
        if submitted:
            raise UserError(self.env._(
                "%s has been submitted and cannot be deleted. Cancel it "
                "instead - the number stays and so does the history.",
                ", ".join(submitted.mapped('display_name'))))
