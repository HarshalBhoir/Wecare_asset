# -*- coding: utf-8 -*-

import logging
import werkzeug
import json
import openerp
import datetime

from openerp.addons.auth_signup.res_users import SignupError
from openerp.addons.web.controllers.main import ensure_db
from openerp import http,tools
from openerp.http import request
from openerp.tools.translate import _
from openerp.addons.auth_signup.controllers.main import AuthSignupHome
from psycopg2 import IntegrityError
from openerp import http, SUPERUSER_ID
from openerp.exceptions import ValidationError
from openerp.addons.base.ir.ir_qweb import nl2br
import base64

_logger = logging.getLogger(__name__)
from openerp.addons.website_portal.controllers.main import website_account


class website_account(website_account):
	@http.route(['/my/home'], type='http', auth="user", website=True)
	def account(self, **kw):
		""" Add sales documents to main account page """
		response = super(website_account, self).account()
		print "Responce",response.qcontext
		partner = request.env.user.partner_id

		leads = request.env['crm.lead'].search([
			('partner_id', '=', partner.id),
		])

		response.qcontext.update({
			'leads': leads,
		})
		return response
	
	@http.route(['/my/orders/<int:order>'], type='http', auth="user", website=True)
	def orders_followup(self, order=None):
		partner = request.env['res.users'].browse(request.uid).partner_id
		domain = [
			('partner_id.id', '=', partner.id),
			('id', '=', order)
		]
		domain_lead = [
			('partner_id', '=', partner.id),
			('id', '=', order)
		]
		lead = request.env['crm.lead'].search(domain)
		order = request.env['sale.order'].search(domain)
		invoiced_lines = request.env['account.invoice.line'].search([('invoice_id', 'in', order.invoice_ids.ids)])
		order_invoice_lines = {il.product_id.id: il.invoice_id for il in invoiced_lines}
	
		return request.website.render("website_portal_sale.orders_followup", {
			'lead': lead.sudo(),
			'order': order.sudo(),
			'order_invoice_lines': order_invoice_lines,
		})

	def details_form_validate(self, data):
		error = dict()
		error_message = []
	
		mandatory_billing_fields = ["name", "phone", "email", "street2", "city", "country_id","mobile"]
	
		# Validation
		for field_name in mandatory_billing_fields:
			if not data.get(field_name):
				error[field_name] = 'missing'
	
		# email validation
		if data.get('email') and not tools.single_email_re.match(data.get('email')):
			error["email"] = 'error'
			error_message.append(_('Invalid Email! Please enter a valid email address.'))
	
		# vat validation
		if data.get("vat") and hasattr(request.env["res.partner"], "check_vat"):
			if request.website.company_id.vat_check_vies:
				# force full VIES online check
				check_func = request.env["res.partner"].vies_vat_check
			else:
				# quick and partial off-line checksum validation
				check_func = request.env["res.partner"].simple_vat_check
			vat_country, vat_number = request.env["res.partner"]._split_vat(data.get("vat"))
			if not check_func(vat_country, vat_number):  # simple_vat_check
				error["vat"] = 'error'
		# error message for empty required fields
		if [err for err in error.values() if err == 'missing']:
			error_message.append(_('Some required fields are empty.'))
	
		return error, error_message

class CustomSignup(openerp.addons.web.controllers.main.Home):
	
	@http.route('/web/signup', type='http', auth='public', website=True)
	def web_auth_signup(self, *args, **kw):
		qcontext = self.get_auth_signup_qcontext()
		if not qcontext.get('token') and not qcontext.get('signup_enabled'):
			raise werkzeug.exceptions.NotFound()

		if 'error' not in qcontext and request.httprequest.method == 'POST':
			try:
				# qcontext['error'] = _("Wrong Captcha !!!")
				# if kw.has_key('g-recaptcha-response') and not request.website.is_captcha_valid(kw['g-recaptcha-response']):
				# 	return request.render('auth_signup.signup', qcontext)
				self.do_signup(qcontext)
				return super(AuthSignupHome, self).web_login(*args, **kw)
			except (SignupError, AssertionError), e:
				if request.env["res.users"].sudo().search([("login", "=", qcontext.get("login"))]):
					qcontext["error"] = _("This email already exist in the system.Kindly mail at info@wecarehomesolutions.com for more information")
				elif not request.env["res.users"].sudo().search([("refferal", "=", qcontext.get("referred"))]):
					qcontext["error"] = _("Refferal is not Correct!")
				
				else:
					_logger.error(e.message)
					qcontext['error'] = _("Could not create a new account.")

		return request.render('auth_signup.signup', qcontext)
	
	def do_signup(self, qcontext):
		if qcontext.get('token') and qcontext.get('reset_password_enabled'):
			values = dict((key, qcontext.get(key)) for key in ('login', 'name', 'password'))
			assert any([k for k in values.values()]), "The form was not properly filled in."
			assert values.get('password') == qcontext.get('confirm_password'), "Passwords do not match; please retype them."
			supported_langs = [lang['code'] for lang in request.registry['res.lang'].search_read(request.cr, openerp.SUPERUSER_ID, [], ['code'])]
			if request.lang in supported_langs:
				values['lang'] = request.lang
			self._signup_with_values(qcontext.get('token'), values)
			request.cr.commit()
		else:
			""" Shared helper that creates a res.partner out of a token """
			values = dict((key, qcontext.get(key)) for key in ('login','file', 'name', 'password','dob','customer','phone','mobile','street','street2','city','zip','country_id','c1_name','c1_dob','c2_name','c2_dob','profession','service','geographics','referred','referred_name','source','other_source_by','is_member_guest','sp_offer'))
			referred = values['referred']

			ref_code = request.env['res.users'].sudo().search([('refferal', 'ilike', referred)])
			values1 = {}
			member1_values = {}
			member2_values = {}
			member3_values = {}
			values['is_member_guest'] = 'guest'
			if values['sp_offer'] == 'on':
				values1 = dict((key, qcontext.get(key)) for key in ('m1_name','m2_name','m3_name'))
				if values1['m1_name']:
					member1_values = dict((key, qcontext.get(key)) for key in ('m1_name','m1_dob','m1_phone','m1_email'))
				values.update(member1_values)
				if values1['m2_name']:
					member2_values = dict((key, qcontext.get(key)) for key in ('m2_name','m2_dob','m2_phone','m2_email'))
				values.update(member2_values)
				if values1['m3_name']:
					member3_values = dict((key, qcontext.get(key)) for key in ('m3_name','m3_dob','m3_phone','m3_email'))
				values.update(member3_values)
			
			#,'c1_name','c1_dob','c2_name','c2_dob','m1_name','m1_dob','m1_phone','m1_email','m2_name','m2_dob','m2_phone','m2_email','m3_name','m3_dob','m3_phone','m3_email'
			if values['c1_dob'] == '':
				values['c1_dob'] = False
			if values['c2_dob'] == '':
				values['c2_dob'] = False
			values['customer'] = 1
		
			if referred:
				assert values.get('referred') == ref_code.refferal, "Refferal Code is not Correct!"
		
				if not request.env['res.users'].sudo().search([('refferal', 'ilike', referred)]):
					qcontext["error"] = ("Refferal is not Correct!")
					# return request.render('auth_signup.signup', qcontext)
					raise ValidationError("Test")
			
			assert values.get('password') == qcontext.get('confirm_password'), "Passwords do not match; please retype them."
			supported_langs = [lang['code'] for lang in request.registry['res.lang'].search_read(request.cr, openerp.SUPERUSER_ID, [], ['code'])]
			if request.lang in supported_langs:
				values['lang'] = request.lang
			self._signup_with_values(qcontext.get('token'), values)
			request.cr.commit()

AuthSignupHome.do_signup = CustomSignup.do_signup

class WebsiteVendor(http.Controller):
	@http.route('/website_vendor/<string:model_name>', type='http', auth="public", website=True, methods=['POST'])
	
	def create_vendor(self, model_name, **kwargs):
		model_record = request.env['ir.model'].search([('model', '=', model_name)])
		values = {}
		data = self.extract_data(model_record, ** kwargs)

		name = 'name' in kwargs and kwargs['name'] 
		street = 'address' in kwargs and kwargs['address']
		contact_person = 'contact_person' in kwargs and  kwargs['contact_person'] 
		contact_number = 'contact_number' in kwargs and kwargs['contact_number'] 
		street2 = 'land' in kwargs and kwargs['land'] 
		mobile = 'mobile' in kwargs and kwargs['mobile'] 
		fax = 'fax' in kwargs and kwargs['fax'] 
		email = 'email' in kwargs and kwargs['email']
		name_owner = 'owner_name' in kwargs and kwargs['owner_name'] 
		owner_address = 'owner_address' in kwargs and kwargs['owner_address'] 
		website = 'website' in kwargs and kwargs['website'] 
		service_provided = 'service_provide' in kwargs and kwargs['service_provide'] 
		licence_required = 'licence_required' in kwargs and kwargs['licence_required'] 
		which_authority = 'whom_licence' in kwargs and kwargs['whom_licence'] 
		banker_name = 'banker_name' in kwargs and kwargs['banker_name'] 
		banker_address = 'banker_address' in kwargs and kwargs['banker_address'] 
		pan_number = 'pan_no' in kwargs and kwargs['pan_no'] 
		no_employee = 'no_employees' in kwargs and kwargs['no_employees'] 
		working_hours = 'working_hours' in kwargs and kwargs['working_hours'] 
		employee_insurance = 'employee_insurance' in kwargs and kwargs['employee_insurance'] 
		'file[0]' in kwargs and kwargs['file[0]'].stream.seek(0)
		binary_image_file1 = 'file[0]' in kwargs and base64.b64encode(kwargs['file[0]'].stream.read())
		licence_copy_name = 'file[0]' in kwargs and kwargs['file[0]'].filename
		'file1[0]' in kwargs and kwargs['file1[0]'].stream.seek(0)
		binary_image_file2 = 'file1[0]' in kwargs and base64.b64encode(kwargs['file1[0]'].stream.read())
		service_tax_name =  'file1[0]' in kwargs and kwargs['file1[0]'].filename
		
		values1 = {'name': name,'street':street,'street2':street2,'contact_person':contact_person,
				   'contact_person_number':contact_number, 'mobile': mobile, 'fax': fax, 'email': email,
				   'name_owner' : name_owner, 'owner_address': owner_address, 'website': website,
				   'service_provided': service_provided, 'licence_required': licence_required,
				   'authority_licence': which_authority, 'banker_name':banker_name,
				   'banker_address' : banker_address, 'pan_number': pan_number, 'no_of_employee': no_employee,
				   'working_hours' : working_hours, 'emp_covered_by_insurance': employee_insurance,
				   'supplier' : True,'customer':False,'licency_copy': binary_image_file1,'licence_copy_name':licence_copy_name,
				   'service_tax': binary_image_file2 ,'service_tax_name': service_tax_name,
				   }
		temp = request.env['res.partner'].sudo().create(values1)
		mail_server = request.env['ir.mail_server'].sudo().search([])
		print "TEMP", temp
		body_mail = """
			Hello %s,<br/>
			Thank you for your interest in becoming our Associate.<br/>
			<br/>
			We shall get in touch with you shortly.
			<br/><br/>
			WeCARE Global Home Solutions Pvt. Ltd.<br/>
			<i>Sambhal Lenge....Apno Jaise</i>
		"""%(name,)
		subject = "Request for Associate"
		values = {
					'model': model_name,
					'res_id': temp.id,
					'email_to': email,
					'email_cc': mail_server.cc,
					'subject': subject,
					'body_html': body_mail,
					'auto_delete': True,
				}
		mail_id = request.env['mail.mail'].sudo().create(values)
		mail_id.sudo().send()
		# full_body = """
		# 	Hello <br/>
		# 	%s is requested for become associate<br/>
		# 	<br/>
		# """%(name,)
		# composed_mail = request.env['mail.mail'].sudo().create({
		# 			'model': model_name,
		# 			'res_id': temp.id,
		# 			'email_to': 'info@wecarehomesolutions.com',
		# 			'subject': subject,
		# 			'body_html': full_body,
		# 			'auto_delete': True,
		# 		})
		# composed_mail.sudo().send()
		return json.dumps({'id': temp.id})
		# # return request.website.render("website.404")
	
	def extract_data(self, model, **kwargs):
	
		data = {
			'record': {},        # Values to create record
			'attachments': [],  # Attached files
			'custom': '',        # Custom fields values
		}
	
		authorized_fields = model.sudo()._get_form_writable_fields()
		print "AUTHORISED FIELDS", authorized_fields
		error_fields = []
	
		for field_name, field_value in kwargs.items():
			# If the value of the field if a file
			if hasattr(field_value, 'filename'):
				# Undo file upload field name indexing
				field_name = field_name.rsplit('[', 1)[0]
	
				# If it's an actual binary field, convert the input file
				# If it's not, we'll use attachments instead
				if field_name in authorized_fields and authorized_fields[field_name]['type'] == 'binary':
					data['record'][field_name] = base64.b64encode(field_value.read())
				else:
					field_value.field_name = field_name
					data['attachments'].append(field_value)
	
			# If it's a known field
			elif field_name in authorized_fields:
				try:
					input_filter = self._input_filters[authorized_fields[field_name]['type']]
					data['record'][field_name] = input_filter(self, field_name, field_value)
				except ValueError:
					error_fields.append(field_name)
	
			# If it's a custom field
			elif field_name != 'context':
				data['custom'] += "%s : %s\n" % (field_name.decode('utf-8'), field_value)
				print "FIELD NAME", field_name
	
		# Add metadata if enabled
		environ = request.httprequest.headers.environ
		if(request.website.website_form_enable_metadata):
			data['meta'] += "%s : %s\n%s : %s\n%s : %s\n%s : %s\n" % (
				"IP"                , environ.get("REMOTE_ADDR"),
				"USER_AGENT"        , environ.get("HTTP_USER_AGENT"),
				"ACCEPT_LANGUAGE"   , environ.get("HTTP_ACCEPT_LANGUAGE"),
				"REFERER"           , environ.get("HTTP_REFERER")
			)
	
		# This function can be defined on any model to provide
		# a model-specific filtering of the record values
		# Example:
		# def website_form_input_filter(self, values):
		#     values['name'] = '%s\'s Application' % values['partner_name']
		#     return values
		dest_model = request.env[model.model]
		if hasattr(dest_model, "website_form_input_filter"):
			data['record'] = dest_model.website_form_input_filter(request, data['record'])
	
		missing_required_fields = [label for label, field in authorized_fields.iteritems() if field['required'] and not label in data['record']]
		if any(error_fields):
			raise ValidationError(error_fields + missing_required_fields)

		return data
	

class WebsiteLead(http.Controller):

	# Check and insert values from the form on the model <model>
	@http.route('/website_lead/<string:model_name>', type='http', auth="user", website=True, methods=['POST'])
	def create_lead(self, model_name, **kwargs):
		model_record = request.env['ir.model'].sudo().search([('model', '=', model_name)])
		values = {}
		data = self.extract_data(model_record, ** kwargs)
		for field in data:
			if kwargs.get(field):
				values[field] = kwargs.pop(field)
		values.update(kwargs=kwargs.items())
		tuple_vals = values['kwargs']
		
# # # # # # # # # # # # # # # #
		l1 = []
		l2 = []
		d1 = {}
		for record in tuple_vals:
			if ":" in record[0]:
				test = record[0].split(":")
				d1[int(test[0])] = (test[1],record[1])
			else:
				l2.append((record[0],record[1]))
		
		for key in sorted(d1):
			l1.append(d1[key])
		
# # # # # # # # # # # # # # # #
		
		final_l = l1 + l2
		
		line_html = ""
		body = """"""
		body_mail = """"""
		subject = ""
		number = 0
		body_desc = """"""
		body_diff_desc = """"""
		body_acc = """"""
				
		code = kwargs['code']
		description = request.env['auto.responce'].sudo().search([('name', '=', code)])
		
		desc = description[0].description
		diff_desc = description[0].diff_desc
		acc = description[0].account
		box =  description[0].box

		if desc:
			body_desc = """
				%s
			"""% (desc)
		if diff_desc:
			body_diff_desc = """
				%s
			"""% (diff_desc)
		if acc:
			body_acc = """
				%s
			"""% (acc)
		
		if box == True:
			for vals in final_l:
				number += 1
				if vals[0] not in ['name','code']:
					line_html += """
						<tr>
							<td style="border: 1px solid black; padding-left: 5px; padding-right: 5px;">%s</td>
							<td style="border: 1px solid black; padding-left: 5px; padding-right: 5px; word-break: break-word;">%s</td>
						</tr>
						""" % (vals[0], vals[1])
		
			body = """
					<table class="table">
						<tbody>
							<tr class="text-center">
								
								<th style="border: 1px solid black; padding-left: 5px; padding-right: 5px;">
									Particulars
								</th>
								<th style="border: 1px solid black; padding-left: 5px; padding-right: 5px;">
									Information
								</th>
							</tr>
							%s
						</tbody>
					</table>
				""" % (line_html)
			
		# body1 = """
		# 		<table class="table">
		# 			<tbody>
		# 				<tr class="text-center">
		# 					<th style="border: 1px solid black; padding-left: 5px; padding-right: 5px;">
		# 						Information
		# 					</th>
		# 				</tr>
		# 				%s
		# 			</tbody>
		# 		</table>
		# 	""" % (line_html1)
		
		assert any([k for k in values.values()]), "The form was not properly filled in."
		
		bank_account = request.env['res.partner.bank'].sudo().search([('company_id', '=', 1)])
		if len(bank_account) > 1:
			bank_account = bank_account[0]
		
		bank = request.env['res.bank'].sudo().search([])
		if len(bank) > 1:
			bank = bank[0]
			
		lead = kwargs['name']
		values1 = {'name': lead,'partner_id':request.env.user.partner_id.id,'html':body}
		temp123 = request.env['crm.lead'].sudo().create(values1)
		body_mail1 = """
			<style>
table tr th, table tr th {
	vertical-align: top !important;
}
			</style>
			Hello %s,<br/>
			%s<br/>
			<br/>
			%s
			<br/>
			%s<br/>
			%s <br/>
		"""%(request.env.user.partner_id.name, body_desc, body, body_diff_desc, body_acc )
		
		# body_mail2 = """
		# 	Hello %s,<br/>
		# 	Your request for <b>"%s"</b> has been received with following information: <br/>
		# 	<br/>
		# 	%s
		# 	<br/>
		# 	We shall revert to you shortly with information and charges for <b>"%s"</b> required by you.
		# 	<br/><br/>
		# 	Customer Support<br/>
		# 	WeCARE Global Home Solutions Pvt. Ltd.<br/>
		# 	<i>Sambhal Lenge....Apno Jaise</i>
		# """%(request.env.user.partner_id.name, lead, body1, lead)
		# 
		# body_mail3 = """
		# 	Hello %s,<br/>
		# 	Your request for <b>"%s"</b> has been received with following particulars: <br/>
		# 	<br/>
		# 	%s
		# 	<br/>
		# 	We shall revert to you shortly with information and charges for the <b>"%s"</b> service required by you.
		# 	<br/><br/>
		# 	Customer Support<br/>
		# 	WeCARE Global Home Solutions Pvt. Ltd.<br/>
		# 	<i>Sambhal Lenge....Apno Jaise</i>
		# """%(request.env.user.partner_id.name, lead, body, lead)
		# 
		# body_mail4 = """
		# 	Hello %s,<br/>
		# 	Your request for <b>"%s"</b> has been received with following information: <br/>
		# 	<br/>
		# 	%s
		# 	<br/>
		# 	We shall revert to you shortly with information and charges for <b>"%s"</b> required by you.
		# 	<br/><br/>
		# 	Customer Support<br/>
		# 	WeCARE Global Home Solutions Pvt. Ltd.<br/>
		# 	<i>Sambhal Lenge....Apno Jaise</i>
		# """%(request.env.user.partner_id.name, lead, body1, lead)
		# 
		# body_mail5 = """
		# 	Hello %s,<br/>
		# 	We thank you for your request for service of <b>"%s"</b></br>
		# 	Please remit the amount as specified against serial no.2 of the Proforma invoice mentioned in<b>"%s"  under the “Real Estate Services” </b>page of our website to our following account. <b>Please INTIMATE US the remittance details.</b>
		# 	
		# 	<br/>
		# 	%s
		# 	<br/>
		# 	We request you to remit the amount as specified in the <b>"%s"</b> page of our website to our following account <b>UNDER INTIMATION TO US.</b>
		# 	<br/><br/>
		# 	<b>Name of Account</b> 	: %s <br/>
		# 	<b>Current   A/C.No.</b>&amp;ensp;	: %s <br/>
		# 	<b>Bank</b> &amp;emsp; &amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;: %s <br/>
		# 	&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;ensp;%s <br/>
		# 	&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;ensp;%s, %s, %s, %s, %s <br/>
		# 	<b>SWIFT Code</b>	&amp;emsp;&amp;ensp;: %s
		# 	<br/><br/>
		# 	Customer Support<br/>
		# 	WeCARE Global Home Solutions Pvt. Ltd.<br/>
		# 	<i>Sambhal Lenge....Apno Jaise</i>
		# """%(request.env.user.partner_id.name, lead, body, lead , bank_account.partner_id.name, bank_account.acc_number, bank.name, bank.street, bank.street2, bank.city, bank.zip, bank.state.name, bank.country.name, bank.bic  )
		
		# body_mail = """
		# 	Hello %s,<br/>
		# 	Your request for service of obtaining <b>"%s"</b> has been received with following particulars: <br/>
		# 	<br/>
		# 	%s
		# 	<br/>
		# 	We request you to remit the amount as specified in the <b>"%s"</b> page of our website to our following account <b>UNDER INTIMATION TO US.</b>
		# 	<br/><br/>
		# 	<b>Name of Account</b> 	: %s <br/>
		# 	<b>Current   A/C.No.</b>&amp;ensp;	: %s <br/>
		# 	<b>Bank</b> &amp;emsp; &amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;: %s <br/>
		# 	&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;ensp;%s <br/>
		# 	&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;emsp;&amp;ensp;%s, %s, %s, %s, %s <br/>
		# 	<b>SWIFT Code</b>	&amp;emsp;&amp;ensp;: %s
		# 	<br/><br/>
		# 	Customer Support<br/>
		# 	WeCARE Global Home Solutions Pvt. Ltd.<br/>
		# 	<i>Sambhal Lenge....Apno Jaise</i>
		# """%(request.env.user.partner_id.name, lead, body, lead , bank_account.partner_id.name, bank_account.acc_number, bank.name, bank.street, bank.street2, bank.city, bank.zip, bank.state.name, bank.country.name, bank.bic  )
		# 
		
		subject = "Request of %s" %(lead)
		values = {
					'subject' : subject,
					'body': body_mail1,
					'model': model_name,
					'message_type': 'email',
					'no_auto_thread': False,
					'res_id': temp123.id,
					'partner_ids' : [(6,0,[request.env.user.partner_id.id])],
				}
		mail_id = request.env['mail.message'].sudo().create(values)
		# mail_id.send()
		full_body = """
			Hello <br/>
			%s is requested for %s:<br/><br/>
			%s
			<br/>
		"""%(request.env.user.partner_id.name, lead, body)
		composed_mail = request.env['mail.mail'].sudo().create({
					'model': model_name,
					'res_id': temp123.id,
					'email_to': 'info@wecarehomesolutions.com',
					'subject': subject,
					'body_html': full_body,
					'auto_delete': True,
				})
		#composed_mail.sudo().send()
		return json.dumps({'id': temp123.id})
	
	_custom_label = "%s\n___________\n\n" % _("Custom infos")  # Title for custom fields
	_meta_label = "%s\n________\n\n" % _("Metadata")  # Title for meta data
	
	# Dict of dynamically called filters following type of field to be fault tolerent
	
	def identity(self, field_label, field_input):
		return field_input
	
	def integer(self, field_label, field_input):
		return int(field_input)
	
	def floating(self, field_label, field_input):
		return float(field_input)
	
	def boolean(self, field_label, field_input):
		return bool(field_input)
	
	def binary(self, field_label, field_input):
		return base64.b64encode(field_input.read())
	
	def one2many(self, field_label, field_input):
		return [int(i) for i in field_input.split(',')]
	
	def many2many(self, field_label, field_input, *args):
		return [(args[0] if args else (6,0)) + (self.one2many(field_label, field_input),)]
	
	_input_filters = {
		'char': identity,
		'text': identity,
		'html': identity,
		'datetime': identity,
		'many2one': integer,
		'one2many': one2many,
		'many2many':many2many,
		'selection': identity,
		'boolean': boolean,
		'integer': integer,
		'float': floating,
		'binary': binary,
	}


	# Extract all data sent by the form and sort its on several properties
	def extract_data(self, model, **kwargs):

		data = {
			'record': {},        # Values to create record
			'attachments': [],  # Attached files
			'custom': '',        # Custom fields values
		}

		authorized_fields = model.sudo()._get_form_writable_fields()
		print "AUTHORISED FIELDS", authorized_fields
		error_fields = []

		for field_name, field_value in kwargs.items():
			# If the value of the field if a file
			if hasattr(field_value, 'filename'):
				# Undo file upload field name indexing
				field_name = field_name.rsplit('[', 1)[0]

				# If it's an actual binary field, convert the input file
				# If it's not, we'll use attachments instead
				if field_name in authorized_fields and authorized_fields[field_name]['type'] == 'binary':
					data['record'][field_name] = base64.b64encode(field_value.read())
				else:
					field_value.field_name = field_name
					data['attachments'].append(field_value)

			# If it's a known field
			elif field_name in authorized_fields:
				try:
					input_filter = self._input_filters[authorized_fields[field_name]['type']]
					data['record'][field_name] = input_filter(self, field_name, field_value)
				except ValueError:
					error_fields.append(field_name)

			# If it's a custom field
			elif field_name != 'context':
				data['custom'] += "%s : %s\n" % (field_name.decode('utf-8'), field_value)
				print "FIELD NAME", field_name

		# Add metadata if enabled
		environ = request.httprequest.headers.environ
		if(request.website.website_form_enable_metadata):
			data['meta'] += "%s : %s\n%s : %s\n%s : %s\n%s : %s\n" % (
				"IP"                , environ.get("REMOTE_ADDR"),
				"USER_AGENT"        , environ.get("HTTP_USER_AGENT"),
				"ACCEPT_LANGUAGE"   , environ.get("HTTP_ACCEPT_LANGUAGE"),
				"REFERER"           , environ.get("HTTP_REFERER")
			)

		# This function can be defined on any model to provide
		# a model-specific filtering of the record values
		# Example:
		# def website_form_input_filter(self, values):
		#     values['name'] = '%s\'s Application' % values['partner_name']
		#     return values
		dest_model = request.env[model.model]
		if hasattr(dest_model, "website_form_input_filter"):
			data['record'] = dest_model.website_form_input_filter(request, data['record'])

		missing_required_fields = [label for label, field in authorized_fields.iteritems() if field['required'] and not label in data['record']]
		if any(error_fields):
			raise ValidationError(error_fields + missing_required_fields)

		return data

	def insert_record(self, request, model, values, custom, meta=None):
		record = request.env[model.model].sudo().create(values)

		if custom or meta:
			default_field = model.website_form_default_field_id
			default_field_data = values.get(default_field.name, '')
			custom_content = (default_field_data + "\n\n" if default_field_data else '') \
						   + (self._custom_label + custom + "\n\n" if custom else '') \
						   + (self._meta_label + meta if meta else '')

			# If there is a default field configured for this model, use it.
			# If there isn't, put the custom data in a message instead
			if default_field.name:
				if default_field.ttype == 'html' or model.model == 'mail.mail':
					custom_content = nl2br(custom_content)
				record.update({default_field.name: custom_content})
			else:
				values = {
					'body': nl2br(custom_content),
					'model': model.model,
					'message_type': 'comment',
					'no_auto_thread': False,
					'res_id': record.id,
				}
				mail_id = request.env['mail.message'].sudo().create(values)

		return record.id

	# Link all files attached on the form
	def insert_attachment(self, model, id_record, files):
		orphan_attachment_ids = []
		record = model.env[model.model].browse(id_record)
		authorized_fields = model.sudo()._get_form_writable_fields()
		for file in files:
			custom_field = file.field_name not in authorized_fields
			attachment_value = {
				'name': file.field_name if custom_field else file.filename,
				'datas': base64.encodestring(file.read()),
				'datas_fname': file.filename,
				'res_model': model.model,
				'res_id': record.id,
			}
			attachment_id = request.env['ir.attachment'].sudo().create(attachment_value)
			if attachment_id and not custom_field:
				record.sudo()[file.field_name] = [(4, attachment_id.id)]
			else:
				orphan_attachment_ids.append(attachment_id.id)

		# If some attachments didn't match a field on the model,
		# we create a mail.message to link them to the record
		if orphan_attachment_ids:
			if model.name != 'mail.mail':
				values = {
					'body': _('<p>Attached files : </p>'),
					'model': model.model,
					'message_type': 'comment',
					'no_auto_thread': False,
					'res_id': id_record,
					'attachment_ids': [(6, 0, orphan_attachment_ids)],
				}
				mail_id = request.env['mail.message'].sudo().create(values)
		else:
			# If the model is mail.mail then we have no other choice but to
			# attach the custom binary field files on the attachment_ids field.
			for attachment_id_id in orphan_attachment_ids:
				record.attachment_ids = [(4, attachment_id_id)]
