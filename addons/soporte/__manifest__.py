{ 
    'name': 'Soporte', 
    'description': 'Cambios al modulo de Proyectos', 
    'author': 'Daniel Reis', 
    'depends': ['base','project'],
    'application': False, 
    
    'data': [
    	'views/proyecto.xml'
    ],

    'post_init_hook': 'test_post_init_hook',
}

