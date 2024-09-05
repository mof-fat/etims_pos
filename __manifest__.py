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
    'depends': ['point_of_sale','l10n_ke_etims_vscu'],

    # always loaded
    'data': [
        'views/pos.xml',
        'views/pos_payment_method_views .xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'l10n_ke_etims_vscu_pos/static/src/js/PaymentScreen.js',
            'l10n_ke_etims_vscu_pos/static/src/js/Order.js',
            'l10n_ke_etims_vscu_pos/static/src/xml/OrderReceipt.xml',
        ],
    },
}
