# -*- coding: utf-8 -*-
"""A person's signature, kept once.

A signature is not a property of a box on a page. It is a property of a
person, and copying it onto every request they touch would leave one image
in many places.

So it lives on the user, and the printed page reads it through whoever
actually signed - the submitter, the reviewer, the approver. One image in one
place. When somebody's signature is redrawn, every page printed afterwards
carries the new one and no row has to be found and corrected.

A value copied is a value that disagrees with itself eventually.
"""
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    construction_signature = fields.Image(
        string="Signature", max_width=1024, max_height=512,
        help="Printed on the requests this person submits, reviews or "
             "approves. Uploaded once, not attached to each request.",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        # A person can see their own signature on their preferences page.
        # Without this the field is on the form and reading it as yourself is
        # refused, which is a confusing way to be told about a whitelist.
        return super().SELF_READABLE_FIELDS + ['construction_signature']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        # And can replace it. Asking an administrator to upload somebody's
        # signature for them is how the field stays empty.
        return super().SELF_WRITEABLE_FIELDS + ['construction_signature']
