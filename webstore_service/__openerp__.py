#
# Real Estate by Aqua-Giraffe
#
{
	'name': 'Web Store Services',
	'version': '1.0',
	'author': 'Saurika Makati (AQUAGiraffe - An MSP1 Company)',
	'sequence': 1,
	'category': 'Web Store',
	'description': """
# Web store Services
""",
	'depends': [
		'base',
		'website_form',
		'auth_signup',
		'crm',
		'document',
	],
	'data': [
		'security/ir.model.access.csv',
		'data/webstore_data.xml',
		'views/res_partner_view.xml',
		'views/website_form_view.xml',
		'views/documents_view.xml',
		'views/auto_responce_view.xml',
		'views/templates.xml',
		'sequence/web_sequence.xml',
		'res_users_template.xml',
		# 'views/webstore_menus.xml',
	],
	'installable' : True,
	'application' : True,
}
