from openerp import models,fields,api,SUPERUSER_ID,tools,_
from datetime import datetime,date,timedelta
from dateutil.relativedelta import relativedelta
from openerp.exceptions import UserError, AccessError
from werkzeug import url_encode, url_decode
import base64


class Partner(models.Model):
	_inherit = 'res.partner'
	
	contact_person = fields.Char(string="Contact Person")
	contact_person_number = fields.Char(string="Contact Person Number")
	name_owner = fields.Char(string="Name of Owner")
	owner_address = fields.Text(string="Address of Owner")
	service_provided = fields.Text(string="Provided Services")
	licence_required = fields.Boolean(string="licence Required?")
	authority_licence = fields.Char(string="From whom/which Authority")
	banker_name = fields.Char(string="Name of Banker")
	banker_address = fields.Text(string="Address of Bankers")
	pan_number = fields.Char(string="PAN Number")
	no_of_employee = fields.Integer(string="Number of Employees")
	working_hours = fields.Text(string="Your Working Hours and Weekly Holidays")
	emp_covered_by_insurance = fields.Char(string="Employees covered by Insurance?")
	licency_copy = fields.Binary(string="Copy of Valid Licence")
	licence_copy_name = fields.Char(string="Licence Copy Name")
	service_tax = fields.Binary(string="Service Tax/VAT/Sales Tax")
	service_tax_name = fields.Char(string="Service Tax Name")
	
	account_type = fields.Selection([('free','Free'),('premium','Premium')], string="Account type", default="free")
	membership_type = fields.Selection([('primary','Primary'),('secondary','Secondary')], string="Membership type")
	subscription_date = fields.Date(string="Subscription date")
	subscription_expiry_date = fields.Date(string="Subscription expiry date")
	
	dob = fields.Date(string="Date of Birth")
	c1_name = fields.Char(string="Name(1st Minor)")
	c1_dob = fields.Date(string="Date of Birth(1st Minor)", default=False)
	c2_name = fields.Char(string="Name(2nd Minor)")
	c2_dob = fields.Date(string="Date of Birth(2nd Minor)", default=False)
	profession = fields.Char(string="Profession")
	service = fields.Char(string="Services")
	geographics = fields.Char(string="Mumbai Geographics")
	refferd_by_code = fields.Char(string="Reffered By")
	reffered_by = fields.Char(string="Referred Name")
	source_id = fields.Many2one('utm.source', string="Source")
	other_source = fields.Char(string="Other Source")
	is_member_guest = fields.Selection([('member','Member'),('guest','Guest')],string="Type")
	register_minor = fields.Boolean(string="Register Minor")
	addon_member = fields.Boolean(string="Add-On Member")
	
	@api.model
	def _cron_birthday_reminder(self):
		su_id =self.env['res.partner'].browse(SUPERUSER_ID)
		bday = self.search([('dob', '!=', False)])
		for partner in bday:
			bdate =datetime.strptime(partner.dob,'%Y-%m-%d').date()
			today =datetime.now().date()
			if bdate == today:
				if bdate.month == today.month:
					if bdate.day == today.day:
						if partner:
							template_id = self.env['ir.model.data'].get_object_reference(
																  'webstore_service',
																  'email_template_edi_birthday_reminder')[1]
							email_template_obj = self.env['mail.template'].browse(template_id)
							if template_id:
								values = email_template_obj.generate_email(partner.id, fields=None)
								values['email_from'] = su_id.email
								values['email_to'] = partner.email
								values['res_id'] = False
								mail_mail_obj = self.env['mail.mail']
								msg_id = mail_mail_obj.create(values)
								if msg_id:
									mail_mail_obj.send([msg_id])
		return True

class res_users_extnds(models.Model):
	_inherit = 'res.users'
	
	def _compute_date(self):
		for rec in self:
			start_date = datetime.strptime(rec.current_create_date, "%Y-%m-%d")
			rec.renew_membership_date = start_date + timedelta(days=363)
	
	def _compute_date_fiften(self):
		for rec in self:
			start_date = datetime.strptime(rec.current_create_date, "%Y-%m-%d")
			rec.renew_member_fiften = start_date + timedelta(days=350)
			
	def _compute_date_fortyfive(self):
		for rec in self:
			start_date = datetime.strptime(rec.current_create_date, "%Y-%m-%d")
			rec.renew_member_fourfive = start_date + timedelta(days=320)
			
	is_member_guest = fields.Selection([('member','Member'),('guest','Guest')],string="Type")
	secondary_member = fields.Boolean(string="Secondary Member")
	parent_member = fields.Many2one('res.users', string="Parent Member")
	refferal = fields.Char(string="Code")
	reffered_by = fields.Char(string="Reffered by")
	refferd_by_code = fields.Char(string="reffered by code")
	renew_membership_date = fields.Date(compute="_compute_date", string="Membership Renewal Date")
	renew_member_fiften = fields.Date(compute="_compute_date_fiften", string="Membership Renewal Date Before 15 Days")
	renew_member_fourfive = fields.Date(compute="_compute_date_fortyfive", string="Membership Renewal Date Before 45 Days")
	current_create_date = fields.Date(string="Create Date", default=datetime.now().date())
	
	@api.multi
	def membership_renewal_notification_fiften(self):
		template = False
		try:
			template = self.env['ir.model.data'].get_object('webstore_service', 'email_template_member_renewal_fiften')
		except ValueError:
			pass
		expiry_date = self.search([('renew_member_fiften', '!=', False)])
		for emp in expiry_date:
			date_closed = datetime.strptime(emp.renew_member_fiften, tools.DEFAULT_SERVER_DATE_FORMAT).date() - relativedelta(days=+15)
			if datetime.today().date() > date_closed:
				template.send_mail(emp.id, raise_exception=True)
				
	@api.multi
	def membership_renewal_notification_fortyfive(self):
		template = False
		try:
			template = self.env['ir.model.data'].get_object('webstore_service', 'email_template_member_renewal_fortyfive')
		except ValueError:
			pass
		expiry_date = self.search([('renew_member_fourfive', '!=', False)])
		for emp in expiry_date:
			date_closed = datetime.strptime(emp.renew_member_fourfive, tools.DEFAULT_SERVER_DATE_FORMAT).date() - relativedelta(days=+45)
			if datetime.today().date() > date_closed:
				template.send_mail(emp.id, raise_exception=True)
				
				
	@api.model
	def create(self, vals):
		vals['refferal'] = self.env['ir.sequence'].next_by_code('res.users') or 'New'
		user_id = super(res_users_extnds,self).create(vals)
		if user_id.is_member_guest == 'guest':
			
			body_mail = """
				Hello %s,<br/>
				Welcome to WeCARE.<br/>
				Thank you for being our Guest. You will enjoy the immense convenience of handling your India affairs efficiently, smoothly and conveniently. <br/>
				Please write to us at info@wecarehomesolutions.com for any queries that you may have.
				<br/><br/>
				Customer Support<br/>
				WeCARE Global Home Solutions Pvt. Ltd.<br/>
				<i>Sambhal Lenge....Apno Jaise</i>
				<p> <img alt="" src="/webstore_service/static/src/img/logo.png" height="169" width="177" float: left;/> </p>
				"""%(user_id.partner_id.name)
			subject = "Welcome to wecare"
			values = {
						'subject' : subject,
						'body_html': body_mail,
						# 'model': 'res.users',
						'message_type': 'email',
						'no_auto_thread': False,
						# 'res_id': user_id.id,
						'email_to': user_id.partner_id.email,
					}
			mail_id = self.env['mail.mail'].sudo().create(values)			
		else:
			bank_account = self.env['res.partner.bank'].sudo().search([('company_id', '=', 1)])
			if len(bank_account) > 1:
				bank_account = bank_account[0]
			
			bank = self.env['res.bank'].sudo().search([])
			if len(bank) > 1:
				bank = bank[0]
			body_mail = """
				Hello %s,<br/>
				Welcome to WeCARE.<br/>
				You will enjoy the immense convenience of handling your India affairs efficiently, smoothly and conveniently.<br/>
				Your membership will be activated as soon as we have your remittance details from our bank.<br/>
				For your ready reference, we give below our bank details:<br/>
				<br/><br/>
				<b>Name of Account</b> 	: %s <br/>
				<b>Current   A/C.No.</b>&ensp;	: %s <br/>
				<b>Bank</b> &emsp; &emsp;&emsp;&emsp;&emsp;&emsp;: %s <br/>
				&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&emsp;%s <br/>
				&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&emsp;%s, %s, %s, %s, %s <br/>
				<b>SWIFT Code</b>	&emsp;&ensp;&emsp;: %s
				<br/><br/>
				Please write to us at <a href="mailto:info@wecarehomesolutions.com">info@wecarehomesolutions.com<a/> for any queries that you may have.<br/><br/>
				Customer Support<br/>
				WeCARE Global Home Solutions Pvt. Ltd.<br/>
				<i>Sambhal Lenge....Apno Jaise</i>
				<p> <img alt="" src="/webstore_service/static/src/img/logo.png" height="169" width="177" float: left;/> </p>
			"""%(user_id.partner_id.name, bank_account.partner_id.name, bank_account.acc_number, bank.name, bank.street, bank.street2, bank.city, bank.zip, bank.state.name, bank.country.name, bank.bic)
			subject = "Welcome to wecare"
			values = {
						'subject' : subject,
						'body_html': body_mail,
						# 'model': 'res.users',
						'message_type': 'email',
						'no_auto_thread': False,
						# 'res_id': user_id.id,
						'email_to': user_id.partner_id.email,
					}
			mail_id = self.env['mail.mail'].sudo().create(values)			
		return user_id
		
		
	@api.multi
	def membership_renewal_notification(self):
		template = False
		try:
			template = self.env['ir.model.data'].get_object('webstore_service', 'email_template_member_renewal')
		except ValueError:
			pass
		expiry_date = self.search([('renew_membership_date', '!=', False)])
		for emp in expiry_date:
			date_closed = datetime.strptime(emp.renew_membership_date, tools.DEFAULT_SERVER_DATE_FORMAT).date() - relativedelta(days=+3)
			if datetime.today().date() > date_closed:
				template.send_mail(emp.id, raise_exception=True)

	@api.multi
	def mail_send(self):
		self.ensure_one()
		ir_model_data = self.env['ir.model.data']
		try:
			compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
		except ValueError:
			compose_form_id = False
		ctx = dict()
		return {
			'type': 'ir.actions.act_window',
			'view_type': 'form',
			'view_mode': 'form',
			'res_model': 'mail.compose.message',
			'views': [(compose_form_id, 'form')],
			'view_id': compose_form_id,
			'target': 'new',
			'context': ctx,
		}


	@api.model
	def _signup_create_user(self, values):
		for key, value in values.items():
			if key == 'file':
				values['file'].stream.seek(0)
				binary_image = base64.b64encode(values['file'].stream.read())
				if 'file' in values:
					values['image'] = binary_image
					
		# if not values['customer'] == True:
		# 	values['file'].stream.seek(0)
		# 	binary_image = base64.b64encode(values['file'].stream.read())
		# 	if 'file' in values:
		# 		values['image'] = binary_image
		
		m1_var = {}
		m2_var = {}
		m3_var = {}
		customer = True
		values['is_member_guest'] = 'guest'
		values['customer'] = True
		if 'secondary_member' in values:
			values.pop('secondary_member')
			return self._signup_create_user(values)
		if 'm1_name' in values and 'm1_dob' in values and 'm1_phone' in values and 'm1_email' in values:
			m1_var = {'name':values['m1_name'], 'dob': values['m1_dob'], 'phone':values['m1_phone'], 'email':values['m1_email'],'login':values['m1_email'], 'secondary_member': True, 'customer': True}
			values.pop('m1_name')
			values.pop('m1_dob')
			values.pop('m1_phone')
			values.pop('m1_email')
		if 'm2_name' in values and 'm2_dob' in values and 'm2_phone' in values and 'm2_email' in values:
			m2_var = {'name':values['m2_name'], 'dob': values['m2_dob'], 'phone':values['m2_phone'], 'email':values['m2_email'],'login':values['m2_email'], 'secondary_member': True, 'customer': True}
			values.pop('m2_name')
			values.pop('m2_dob')
			values.pop('m2_phone')
			values.pop('m2_email')
		if 'm3_name' in values and 'm3_dob' in values and 'm3_phone' in values and 'm3_email' in values:
			m3_var = {'name':values['m3_name'], 'dob': values['m3_dob'], 'phone':values['m3_phone'], 'email':values['m3_email'],'login':values['m3_email'], 'secondary_member': True, 'customer': True}
			values.pop('m3_name')
			values.pop('m3_dob')
			values.pop('m3_phone')
			values.pop('m3_email')
		# return False
		res = super(res_users_extnds, self)._signup_create_user(values)
		# values['customer'] = True
		for member in [m1_var, m2_var, m3_var]:
			if bool(member):
				member['parent_member'] = res
				self._signup_create_user(member)
		return res
	

class cre_lead_extension(models.Model):
	_inherit = 'crm.lead'
	
	html = fields.Html(string="Lead")

	def website_form_input_filter(self, request, values):
		values = super(cre_lead_extension, self).website_form_input_filter(request, values)
		values['source_id'] = (
				values.get('source_id') or
				self.sudo().env['ir.model.data'].xmlid_to_res_id('webstore_service.source_contactus')
		)
		return values

	@api.model
	def create(self, vals):
		result = super(cre_lead_extension, self).create(vals)
		if result.source_id:
			body_mail = """
				Hi %s,<br/>
				We have received your message.
				We shall contact you shortly.
				<br/><br/>
				Team WeCARE<br/>
				<p> <img alt="" src="/webstore_service/static/src/img/logo.png" height="169" width="177" float: left;/> </p>
				"""%(result.contact_name)
			subject = "contact us"
			values = {
						'subject' : subject,
						'body_html': body_mail,
						'model': 'crm.lead',
						'message_type': 'email',
						'no_auto_thread': False,
						'res_id': result.id,
						'email_to': result.email_from,
					}
			mail_id = self.env['mail.mail'].sudo().create(values)			
		return result

	
class ir_mail_server_extension(models.Model):
	_inherit = 'ir.mail_server'	
	
	cc = fields.Char(string="Email CC")

	