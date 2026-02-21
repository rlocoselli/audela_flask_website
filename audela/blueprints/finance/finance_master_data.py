"""
Routes pour la gestion des données maîtres financières:
- Produits (FinanceProduct)
- Contreparties (FinanceCounterparty)
- Configuration IBAN
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, abort, session
from flask_login import current_user, login_required
from sqlalchemy import func
from decimal import Decimal
from datetime import datetime

from ...extensions import db
from ...models.finance import FinanceCompany
from ...models.finance_ref import FinanceCounterparty
from ...models.finance_ext import FinanceProduct
from ...i18n import DEFAULT_LANG, tr
from ...tenancy import get_current_tenant_id
from ...services.bank_configuration_service import IBANValidator, BankConfigurationService
from ...security import require_roles


finance_master_bp = Blueprint('finance_master', __name__, url_prefix='/finance/master')


def _(msgid: str, **kwargs):
    """Shortcut for translations."""
    return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)


def _require_tenant() -> None:
    """Ensure user is authenticated and belongs to a tenant."""
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(g, "tenant", None) or current_user.tenant_id != g.tenant.id:
        abort(403)


def _get_company() -> FinanceCompany:
    """Récupérer la compagnie sélectionnée du tenant."""
    _require_tenant()
    
    company_id = request.args.get('company_id') or session.get('finance_company_id')
    if not company_id:
        company = FinanceCompany.query.filter_by(tenant_id=g.tenant.id).first()
        if not company:
            abort(404)
        company_id = company.id
    
    company = FinanceCompany.query.filter_by(
        id=company_id,
        tenant_id=g.tenant.id
    ).first()
    
    if not company:
        abort(403)
    
    return company


# ============================================================================
# DASHBOARD PRINCIPAL
# ============================================================================

@finance_master_bp.route('/master', methods=['GET'])
@login_required
def master_dashboard():
    """Dashboard principal de gestion financière."""
    company = _get_company()
    
    # Statistiques
    products_count = FinanceProduct.query.filter_by(company_id=company.id).count()
    counterparties_count = FinanceCounterparty.query.filter_by(tenant_id=g.tenant.id).count()
    company_has_iban = bool(getattr(company, 'iban', None))
    gocardless_configured = False  # TODO: vérifier si connection existe
    
    return render_template(
        'finance/master_dashboard.html',
        company=company,
        products_count=products_count,
        counterparties_count=counterparties_count,
        company_has_iban=company_has_iban,
        gocardless_configured=gocardless_configured
    )


# ============================================================================
# PRODUITS (FinanceProduct)
# ============================================================================

@finance_master_bp.route('/products', methods=['GET'])
@login_required
def list_products():
    """Lister tous les produits pour la compagnie."""
    company = _get_company()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = FinanceProduct.query.filter_by(tenant_id=g.tenant.id, company_id=company.id)
    
    if search:
        query = query.filter(
            (FinanceProduct.name.ilike(f'%{search}%')) |
            (FinanceProduct.code.ilike(f'%{search}%'))
        )
    
    products = query.paginate(page=page, per_page=20)
    
    return render_template(
        'finance/products/list.html',
        products=products,
        company=company,
        search=search
    )


@finance_master_bp.route('/products/create', methods=['GET', 'POST'])
@login_required
def create_product():
    """Créer un nouveau produit."""
    company = _get_company()
    
    if request.method == 'POST':
        form_data = request.form
        
        # Validation
        name = form_data.get('name', '').strip()
        code = form_data.get('code', '').strip()
        description = form_data.get('description', '').strip()
        
        if not name:
            flash(_('Nome é obrigatório'), 'error')
            return redirect(url_for('finance_master.create_product', company_id=company.id))
        
        # Vérifier unicité du code si fourni
        if code and FinanceProduct.query.filter_by(
            tenant_id=g.tenant.id,
            company_id=company.id,
            code=code
        ).first():
            flash(_('Slug já existe'), 'error')
            return redirect(url_for('finance_master.create_product', company_id=company.id))
        
        # Pricing + currency (required by model)
        try:
            unit_price = Decimal((form_data.get('unit_price') or '0').strip() or '0')
        except (ValueError, TypeError):
            flash(_('Dados inválidos'), 'error')
            return redirect(url_for('finance_master.create_product', company_id=company.id))
        currency_code = ((form_data.get('currency_code') or getattr(company, 'base_currency', None) or 'EUR').strip().upper())[:8]

        # VAT Configuration
        try:
            vat_applies = form_data.get('vat_applies') == 'on'
            vat_rate = Decimal(form_data.get('vat_rate', '20.0')) if vat_applies else Decimal('0')
            tax_exempt_reason = form_data.get('tax_exempt_reason', '').strip() if not vat_applies else ''
        except (ValueError, TypeError):
            flash(_('Dados inválidos'), 'error')
            return redirect(url_for('finance_master.create_product', company_id=company.id))
        
        # Créer le produit
        try:
            product = FinanceProduct(
                tenant_id=g.tenant.id,
                company_id=company.id,
                name=name,
                code=code,
                description=description,
                unit_price=unit_price,
                currency_code=currency_code,
                vat_applies=vat_applies,
                vat_rate=vat_rate,
                tax_exempt_reason=tax_exempt_reason,
            )
            
            db.session.add(product)
            db.session.commit()
            
            flash(_('Produto criado com sucesso'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Erro ao criar produto'), 'error')
        
        return redirect(url_for('finance_master.list_products', company_id=company.id))
    
    return render_template(
        'finance/products/create.html',
        company=company
    )


@finance_master_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Éditer un produit existant."""
    company = _get_company()
    
    product = FinanceProduct.query.filter_by(
        id=product_id,
        tenant_id=g.tenant.id,
        company_id=company.id
    ).first()
    
    if not product:
        abort(404)
    
    if request.method == 'POST':
        form_data = request.form
        
        product.name = form_data.get('name', '').strip() or product.name
        product.description = form_data.get('description', '').strip() or product.description
        
        # VAT
        try:
            product.vat_applies = form_data.get('vat_applies') == 'on'
            if product.vat_applies:
                try:
                    product.vat_rate = Decimal(form_data.get('vat_rate', '20.0'))
                except (ValueError, TypeError):
                    flash(_('Dados inválidos'), 'error')
                    return redirect(url_for(
                        'finance_master.edit_product',
                        product_id=product_id
                    ))
                product.tax_exempt_reason = ''
            else:
                product.vat_rate = Decimal('0')
                product.tax_exempt_reason = form_data.get('tax_exempt_reason', '').strip()
            
            product.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash(_('Produto atualizado com sucesso'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Erro ao atualizar produto'), 'error')
        
        return redirect(url_for('finance_master.list_products', company_id=company.id))
    
    return render_template(
        'finance/products/edit.html',
        product=product,
        company=company
    )


@finance_master_bp.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    """Supprimer un produit."""
    company = _get_company()
    
    product = FinanceProduct.query.filter_by(
        id=product_id,
        tenant_id=g.tenant.id,
        company_id=company.id
    ).first()
    
    if not product:
        abort(404)
    
    try:
        db.session.delete(product)
        db.session.commit()
        flash(_('Produto removido com sucesso'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Erro ao remover produto'), 'error')
    
    return redirect(url_for('finance_master.list_products', company_id=company.id))


# ============================================================================
# CONTREPARTIES (FinanceCounterparty)
# ============================================================================

@finance_master_bp.route('/counterparties', methods=['GET'])
@login_required
def list_counterparties():
    """Lister les contreparties."""
    company = _get_company()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = FinanceCounterparty.query.filter_by(tenant_id=g.tenant.id)
    
    if search:
        query = query.filter(
            (FinanceCounterparty.name.ilike(f'%{search}%')) |
            (FinanceCounterparty.tax_id.ilike(f'%{search}%')) |
            (FinanceCounterparty.iban.ilike(f'%{search}%'))
        )
    
    counterparties = query.paginate(page=page, per_page=20)
    
    return render_template(
        'finance/counterparties/list.html',
        counterparties=counterparties,
        company=company,
        search=search
    )


@finance_master_bp.route('/counterparties/create', methods=['GET', 'POST'])
@login_required
def create_counterparty():
    """Créer une nouvelle contrepartie."""
    company = _get_company()
    
    if request.method == 'POST':
        form_data = request.form
        
        name = form_data.get('name', '').strip()
        if not name:
            flash(_('Nome é obrigatório'), 'error')
            return redirect(url_for('finance_master.create_counterparty'))
        
        # IBAN optionnel
        iban = form_data.get('iban', '').strip()
        if iban:
            is_valid, msg = IBANValidator.is_valid(iban)
            if not is_valid:
                flash(_(f'IBAN inválido: {msg}'), 'error')
                return redirect(url_for('finance_master.create_counterparty'))
        
        counterparty = FinanceCounterparty(
            tenant_id=g.tenant.id,
            name=name,
            tax_id=form_data.get('tax_id', '').strip(),
            iban=iban,
            bic=form_data.get('bic', '').strip(),
            email=form_data.get('email', '').strip(),
            phone=form_data.get('phone', '').strip(),
            address=form_data.get('address', '').strip(),
            country_code=form_data.get('country_code', '').strip(),
            created_by=current_user.id,
            created_at=datetime.utcnow()
        )
        
        try:
            db.session.add(counterparty)
            db.session.commit()
            
            flash(_('Contraparte criada com sucesso'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Erro ao criar contraparte'), 'error')
        
        return redirect(url_for('finance_master.list_counterparties', company_id=company.id))
    
    return render_template(
        'finance/counterparties/create.html',
        company=company
    )


@finance_master_bp.route('/counterparties/<int:counterparty_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_counterparty(counterparty_id):
    """Éditer une contrepartie."""
    company = _get_company()
    
    counterparty = FinanceCounterparty.query.filter_by(
        id=counterparty_id,
        tenant_id=g.tenant.id
    ).first()
    
    if not counterparty:
        abort(404)
    
    if request.method == 'POST':
        form_data = request.form
        
        counterparty.name = form_data.get('name', '').strip() or counterparty.name
        
        # IBAN
        iban = form_data.get('iban', '').strip()
        if iban and iban != counterparty.iban:
            is_valid, msg = IBANValidator.is_valid(iban)
            if not is_valid:
                flash(_(f'IBAN invalide: {msg}'), 'error')
                return redirect(url_for(
                    'finance_master.edit_counterparty',
                    counterparty_id=counterparty_id
                ))
            counterparty.iban = iban
        
        counterparty.tax_id = form_data.get('tax_id', '').strip() or counterparty.tax_id
        counterparty.bic = form_data.get('bic', '').strip() or counterparty.bic
        counterparty.email = form_data.get('email', '').strip() or counterparty.email
        counterparty.phone = form_data.get('phone', '').strip() or counterparty.phone
        counterparty.address = form_data.get('address', '').strip() or counterparty.address
        counterparty.country_code = form_data.get('country_code', '').strip() or counterparty.country_code
        counterparty.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
            
            flash(_('Contraparte atualizada com sucesso'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Erro ao atualizar contraparte'), 'error')
        
        return redirect(url_for('finance_master.list_counterparties', company_id=company.id))
    
    return render_template(
        'finance/counterparties/edit.html',
        counterparty=counterparty,
        company=company
    )


@finance_master_bp.route('/counterparties/<int:counterparty_id>/delete', methods=['POST'])
@login_required
def delete_counterparty(counterparty_id):
    """Supprimer une contrepartie."""
    company = _get_company()
    
    counterparty = FinanceCounterparty.query.filter_by(
        id=counterparty_id,
        tenant_id=g.tenant.id
    ).first()
    
    if not counterparty:
        abort(404)
    
    try:
        db.session.delete(counterparty)
        db.session.commit()
        flash(_('Contraparte removida com sucesso'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Erro ao remover contraparte'), 'error')
    
    return redirect(url_for('finance_master.list_counterparties', company_id=company.id))


# ============================================================================
# CONFIGURATION BANCAIRE
# ============================================================================

@finance_master_bp.route('/bank-config', methods=['GET'])
@login_required
def bank_config():
    """Configuration IBAN et GoCardless."""
    from ...models.finance import FinanceAccount
    
    company = _get_company()
    
    config = None
    if hasattr(company, 'iban') and company.iban:
        config = {
            'iban': company.iban,
            'formatted_iban': IBANValidator.format_iban(company.iban)
        }
    
    # Récupérer les comptes de la compagnie avec leurs IBANs
    accounts = FinanceAccount.query.filter_by(
        company_id=company.id,
        tenant_id=g.tenant.id
    ).all()
    
    # Formater les IBANs pour affichage
    for account in accounts:
        if account.iban:
            account.formatted_iban = IBANValidator.format_iban(account.iban)
    
    return render_template(
        'finance/bank_config.html',
        company=company,
        config=config,
        accounts=accounts
    )


@finance_master_bp.route('/bank-config/iban', methods=['POST'])
@login_required
def set_iban():
    """Configurer IBAN pour la compagnie."""
    company = _get_company()
    
    iban = request.form.get('iban', '').strip()
    account_id = request.form.get('account_id', '').strip()
    
    if not iban:
        flash(_('IBAN é requerido'), 'error')
        return redirect(url_for('finance_master.bank_config', company_id=company.id))
    
    is_valid, msg = IBANValidator.is_valid(iban)
    if not is_valid:
        flash(_(f'IBAN inválido: {msg}'), 'error')
        return redirect(url_for('finance_master.bank_config', company_id=company.id))
    
    try:
        # Se tem account_id, configurer IBAN para o account
        if account_id:
            from ...models.finance import FinanceAccount
            account = FinanceAccount.query.get(int(account_id))
            if not account or account.company_id != company.id:
                flash(_('Conta não encontrada'), 'error')
            else:
                result = BankConfigurationService.configure_account_iban(
                    account_id=int(account_id),
                    iban=iban
                )
                if result['status'] == 'success':
                    db.session.commit()
                    flash(_('Configuração Salva'), 'success')
                else:
                    flash(result['message'], 'error')
        else:
            # Caso contrário, configurar IBAN da compagnia
            result = BankConfigurationService.configure_company_iban(
                company_id=company.id,
                iban=iban
            )
            if result['status'] == 'success':
                db.session.commit()
                flash(_('Configuração Salva'), 'success')
            else:
                flash(result['message'], 'error')
    except Exception as e:
        db.session.rollback()
        flash(_('Erro ao Salvar Configuração'), 'error')
    
    return redirect(url_for('finance_master.bank_config', company_id=company.id))


@finance_master_bp.route('/api/validate-iban', methods=['POST'])
@login_required
def validate_iban_api():
    """API pour valider IBAN en temps réel."""
    data = request.get_json()
    iban = data.get('iban', '').strip()
    
    if not iban:
        return jsonify({'valid': False, 'message': 'IBAN required'}), 400
    
    is_valid, message = IBANValidator.is_valid(iban)
    
    if is_valid:
        formatted = IBANValidator.format_iban(iban)
        return jsonify({
            'valid': True,
            'message': 'Valid IBAN',
            'formatted': formatted
        })
    
    return jsonify({
        'valid': False,
        'message': message
    })
