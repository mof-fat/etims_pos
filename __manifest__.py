# -*- coding: utf-8 -*-
{
    'name': "Etims POS[......]",

    'summary': """
        Integrate etims with pos""",

    'description': """
        Long description of module's purpose
    """,


    'category': 'Point of Sale',
    'version': '16.0.0.1.0',

    # any module necessary for this one to work correctly
    'depends': ['point_of_sale',],

    # always loaded
    'data': [
        'views/pos.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'etims_pos/static/src/js/PaymentScreen.js',
            'etims_pos/static/src/js/Order.js',
            'etims_pos/static/src/xml/OrderReceipt.xml',
        ],
    },
}
