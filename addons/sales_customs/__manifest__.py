{
    "name": "Customización de ventas",
    "summary": "Módulo con customizaciones de lo relacionado con ventas",
    "author": "Tekniu: Isaac, Jehosafat",
    "depends": [
        "base", "point_of_sale", "account", "pos_pay_control"
    ],
    "installable": True,
    "data": [
        'data/assets.xml',
        'views/pos_order_views.xml'
    ],
    "qweb": [
        "base", "point_of_sale", "pos_pay_control"
    ],
    "data": [
        'views/pos_order_views.xml',
        'views/account_payment_views.xml',
    ]
}
