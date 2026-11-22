# -*- coding: utf-8 -*-
{
    'name': "Construction Requests",
    'summary': "Employee and site requests: leave, advance, material, payment",
    'description': """
Construction Requests
=====================

Employee and site requests in one model: leave, advance, material, payment
certificates and more.

Each request has a type, the review chain that type asks for (project engineer,
HR, approver), and the numbering that type uses: one sequence per type, or one
sequence per company and project.
""",
    'author': "Znad-Odoo-DEV",
    'website': "https://github.com/Znad-Odoo-DEV/construction_requests",
    'category': 'Human Resources',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr', 'project', 'stock'],
    'data': [
        'security/construction_requests_groups.xml',
        'security/ir.model.access.csv',
        'security/construction_requests_record_rules.xml',
        'data/construction_request_type_data.xml',
        'views/construction_request_views.xml',
        'views/request_approver_views.xml',
        'views/construction_request_type_views.xml',
        'views/construction_request_sequence_views.xml',
        'views/res_users_views.xml',
        'views/construction_requests_menus.xml',
        'report/construction_request_mr_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'construction_requests/static/src/scss/requests.scss',
        ],
    },
    'application': True,
    'installable': True,
}
