# Construction Requests

Odoo 19 module for employee and site requests in a construction company: leave, advance salary, material requests, payment certificates and more, in one model.

## Features

- One request model with a **type**; thirteen types are provided (material, annual / emergency leave, advance, payment certificate, resignation notice, ...).
- Review chain per type: project engineer / coordinator, HR, final approver, with one security group per step.
- Approver set on the project, with the company as fallback; consultant e-mail addresses on the project.
- Numbering per type, or per company, project and type, with editable prefix and counter.
- Kanban dashboard per type with pending counts, calendar and pivot views.
- Materials requisition PDF with stock available and previous quantities computed.
- Signature stored once on the user and printed on reports.
- Revisions (`-R1`, `-R2`) and sending back with a mandatory reason.

## Dependencies

Odoo 19 modules: `base`, `mail`, `hr`, `project`, `stock`. Related repositories (optional bridges):
`construction_requests_payroll`, `construction_requests_purchase`, `construction_store`.

## Installation

1. Copy this folder into your Odoo 19 addons path.
2. Update the apps list and install **Construction Requests**.
3. Assign users to the groups under *Requests*, and set a request approver on the company and/or projects.

## License

LGPL-3
