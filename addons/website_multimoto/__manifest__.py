# -*- coding: utf-8 -*-

{
    'name': 'Website custom',
    'summary': 'Website custom',
    'sequence': '1',
    'category': 'Website',
    'description': """
This module adds new some features about website and ecommerce portal.""",
    'depends': ['portal', 'point_of_sale', 'purchase'],
    'data': [
        'views/pos_orders.xml',
    ],
    'qweb': [

    ],
}