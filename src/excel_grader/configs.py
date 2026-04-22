
STOCK_CONFIGS = {
        #lab 3 stock
        #"red": 2.0,
        #"blue": 4.0,
        #"yellow": 1.0,
        #Lab 4 stock
        0.5
        }

DILUTION_CONFIGS = {
        10,
        20,
        40,
        80,
        160,
        0
        }

PKA_CONFIGS = {
        'pnp': 7.15,
        }

OPERATION_CONFIGS = {
        #Lab 3 config
        #'stock': {
        #    'source_group': 'stock',
        #    'target_group': 'stock',
        #    'operation': 'verify_stock',
        #    'error_msg': 'stock verification failed'
        #},
        #'concentration': {
        #    'source_group': 'dilution-factor',
        #    'target_group': 'concentration',
        #    'operation': 'division',
        #    'numerator': 'stock_color_concentration',
        #    'error_msg': 'concentration verification failed'
        #},
        #'average': {
        #    'source_group': 'raw',
        #    'target_group': 'average',
        #    'operation': 'mean',
        #    'error_msg': 'average verification failed'
        #},
        #'corrected': {
        #    'source_group': 'average',
        #    'target_group': 'corrected',
        #    'operation': 'blank_correction',
        #    'dilution_col': 'color_concentration_1-3', 
        #    'error_msg': 'corrected verification failed'
        #},
        # Lab 4 config
        'stock-concentration': {
            'source_group': 'stock-concentration',
            'target_group': 'stock-concentration',
            'operation': 'verify_stock',
            'error_msg': 'stock verification failed'
        },
        'dilution': {
            'source_group': 'dilution',
            'target_group': 'dilution',
            'operation': 'verify_dilution_factor',
            'error_msg': 'stock verification failed'
        },
        'concentration': {
            'source_group': 'stock-concentration',
            'target_group': 'diluted-concentration',
            'operation': 'verify_working',
            'dilution_col': 'pnp_dilution_factor', 
            'error_msg': 'Working stock verification failed'
        },
        'average': {
            'source_group': 'raw',
            'target_group': 'average',
            'operation': 'mean',
            'error_msg': 'average verification failed'
        },
        'corrected': {
            'source_group': 'average',
            'target_group': 'corrected',
            'operation': 'blank_correction',
            'dilution_col': 'pnp_diluted-concentration', 
            'error_msg': 'corrected verification failed'
        },
        'graph': {
            'source_group': 'corrected',
            'target_group': 'graph',
            'operation': 'graph',
            'dilution_col': 'pnp_diluted-concentration', 
            'set_y_int_to_0': 'True',
            'error_msg': 'Graph verification failed'
        },
        'hh': {
            'source_group': 'graph',
            'target_group': 'hh',
            'operation': 'verify_hh_ph',
            'dilution_col': 'graph_slope_naoh', 
            'error_msg': 'Hernderson-Hasslebach verification failed'
        },
}
