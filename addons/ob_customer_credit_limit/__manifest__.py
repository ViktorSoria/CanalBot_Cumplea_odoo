# -*- coding: utf-8 -*-
{
    'name': "Customer Credit Limit",
    'summary': """ Configure Credit Limit for Customers""",
    'description': """ Activate and configure credit limit customer wise. If credit limit configured
    the system will warn or block the confirmation of a sales order if the existing due amount is greater
    than the configured warning or blocking credit limit. """,
    'author': "Tekniu",
    'license': 'AGPL-3',
    'category': 'Sales',
    'images': ['static/description/customer_credit_limit.png'],
    'version': '14.0.1.0.0',
    'depends': ['sale_management','account','l10n_mx_edi'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/warning_wizard.xml',
        'wizard/pagare_wizard.xml',
        'wizard/report_pagare.xml',
        'views/res_partner.xml',
        'views/sale_order.xml',
    ],
    'installable': True,
    'auto_install': False,
}