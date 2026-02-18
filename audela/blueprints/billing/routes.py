"""
Billing Routes

Routes pour la gestion des abonnements et paiements.
"""
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
    current_app
)
from flask_login import login_required, current_user

from ...extensions import db
from ...extensions import csrf
from ...models import Tenant
from ...models.subscription import SubscriptionPlan, TenantSubscription, BillingEvent
from ...services.subscription_service import SubscriptionService
from ...tenancy import require_tenant
from ...i18n import tr
from . import bp


@bp.route("/plans")
def plans():
    """Display available subscription plans."""
    plans = SubscriptionService.get_available_plans(include_internal=False)
    selected_product = (request.args.get("product") or "").strip().lower()

    if selected_product == "finance":
        plans = [plan for plan in plans if plan.has_finance]
    elif selected_product == "bi":
        plans = [plan for plan in plans if plan.has_bi]
    else:
        selected_product = None
    
    current_plan = None
    if current_user.is_authenticated:
        tenant = Tenant.query.get(current_user.tenant_id)
        if tenant and tenant.subscription:
            current_plan = tenant.subscription.plan
    
    return render_template(
        "billing/plans.html",
        plans=plans,
        current_plan=current_plan,
        selected_product=selected_product
    )


@bp.route("/subscription")
@login_required
@require_tenant
def subscription():
    """View current subscription details and usage."""
    from ...services.tenant_service import TenantService
    
    tenant = Tenant.query.get(current_user.tenant_id)
    if not tenant:
        flash("Tenant not found", "error")
        return redirect(url_for("portal.home"))
    
    stats = TenantService.get_tenant_stats(current_user.tenant_id)
    
    # Get billing history
    billing_events = BillingEvent.query.filter_by(
        tenant_id=current_user.tenant_id
    ).order_by(
        BillingEvent.created_at.desc()
    ).limit(20).all()
    
    return render_template(
        "billing/subscription.html",
        tenant=tenant,
        subscription=tenant.subscription,
        stats=stats,
        billing_events=billing_events
    )


@bp.route("/upgrade/<plan_code>")
@login_required
@require_tenant
def upgrade(plan_code):
    """Initiate upgrade to a paid plan."""
    plan = SubscriptionPlan.query.filter_by(code=plan_code, is_active=True).first()
    if not plan:
        flash("Plan not found", "error")
        return redirect(url_for("billing.plans"))
    
    tenant = Tenant.query.get(current_user.tenant_id)
    if not tenant:
        flash("Tenant not found", "error")
        return redirect(url_for("portal.home"))
    
    # Check if already on this plan
    if tenant.subscription and tenant.subscription.plan.code == plan_code:
        flash("You are already on this plan", "info")
        return redirect(url_for("billing.subscription"))
    
    return render_template(
        "billing/upgrade.html",
        plan=plan,
        tenant=tenant,
        subscription=tenant.subscription
    )


@bp.route("/checkout", methods=["POST"])
@login_required
@require_tenant
@csrf.exempt
def checkout():
    """Create Stripe checkout session and redirect."""
    plan_code = request.form.get("plan_code")
    billing_cycle = request.form.get("billing_cycle", "monthly")
    
    if not plan_code or billing_cycle not in ["monthly", "yearly"]:
        flash("Invalid plan or billing cycle", "error")
        return redirect(url_for("billing.plans"))
    
    plan = SubscriptionPlan.query.filter_by(code=plan_code, is_active=True).first()
    if not plan:
        flash("Plan not found", "error")
        return redirect(url_for("billing.plans"))

    is_free_plan = (
        plan.code == "free"
        or (
            plan.price_monthly is not None
            and plan.price_yearly is not None
            and plan.price_monthly <= 0
            and plan.price_yearly <= 0
        )
    )

    try:
        if is_free_plan:
            SubscriptionService.upgrade_to_paid(
                tenant_id=current_user.tenant_id,
                plan_code=plan.code,
                billing_cycle="monthly",
                stripe_customer_id=None,
                stripe_subscription_id=None,
            )
            flash("Free plan activated. No card required.", "success")
            return redirect(url_for("billing.subscription"))

        # Create Stripe checkout session
        session_url = SubscriptionService.create_stripe_checkout_session(
            tenant_id=current_user.tenant_id,
            plan_code=plan_code,
            billing_cycle=billing_cycle,
            success_url=url_for("billing.checkout_success", _external=True),
            cancel_url=url_for("billing.checkout_cancel", _external=True)
        )
        
        return redirect(session_url)
    
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("billing.plans"))
    except Exception as e:
        current_app.logger.error(f"Stripe checkout error: {e}")
        flash("Payment processing error. Please try again.", "error")
        return redirect(url_for("billing.plans"))


@bp.route("/checkout/success")
@login_required
@require_tenant
def checkout_success():
    """Handle successful Stripe payment."""
    flash("Payment successful! Your subscription is now active.", "success")
    return redirect(url_for("billing.subscription"))


@bp.route("/checkout/cancel")
@login_required
@require_tenant
def checkout_cancel():
    """Handle cancelled Stripe payment."""
    flash("Payment cancelled. Your subscription was not changed.", "info")
    return redirect(url_for("billing.plans"))


@bp.route("/cancel-subscription", methods=["POST"])
@login_required
@require_tenant
def cancel_subscription():
    """Cancel current subscription."""
    reason = request.form.get("reason", "user_requested")
    
    tenant = Tenant.query.get(current_user.tenant_id)
    if not tenant or not tenant.subscription:
        flash("No active subscription found", "error")
        return redirect(url_for("billing.subscription"))
    
    try:
        SubscriptionService.cancel_subscription(
            tenant_id=current_user.tenant_id,
            reason=reason
        )
        flash("Subscription cancelled successfully", "success")
    except Exception as e:
        current_app.logger.error(f"Cancel subscription error: {e}")
        flash("Error cancelling subscription. Please contact support.", "error")
    
    return redirect(url_for("billing.subscription"))


@bp.route("/webhooks/stripe", methods=["POST"])
def stripe_webhook():
    """
    Handle Stripe webhooks.
    
    Important: This endpoint must be publicly accessible.
    Verify webhook signature with Stripe for security.
    """
    import stripe
    
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        current_app.logger.error(f"Invalid Stripe webhook payload: {e}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        current_app.logger.error(f"Invalid Stripe webhook signature: {e}")
        return jsonify({"error": "Invalid signature"}), 400
    
    # Handle event types
    event_type = event["type"]
    event_data = event["data"]["object"]
    
    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(event_data)
        
        elif event_type == "customer.subscription.created":
            _handle_subscription_created(event_data)
        
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(event_data)
        
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(event_data)
        
        elif event_type == "invoice.payment_succeeded":
            _handle_payment_succeeded(event_data)
        
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(event_data)
        
        else:
            current_app.logger.info(f"Unhandled Stripe event type: {event_type}")
    
    except Exception as e:
        current_app.logger.error(f"Error processing Stripe webhook: {e}")
        return jsonify({"error": "Processing error"}), 500
    
    return jsonify({"status": "success"}), 200


def _handle_checkout_completed(session):
    """Handle successful checkout session."""
    stripe_customer_id = session.get("customer")
    stripe_subscription_id = session.get("subscription")
    
    # Find tenant by Stripe customer ID
    subscription = TenantSubscription.query.filter_by(
        stripe_customer_id=stripe_customer_id
    ).first()
    
    if subscription:
        subscription.stripe_subscription_id = stripe_subscription_id
        subscription.status = "active"
        
        # Create billing event
        db.session.add(BillingEvent(
            tenant_id=subscription.tenant_id,
            event_type="checkout_completed",
            description="Checkout session completed",
            metadata_json={"session_id": session.get("id")},
            stripe_event_id=session.get("id")
        ))
        
        db.session.commit()


def _handle_subscription_created(subscription_data):
    """Handle new subscription creation."""
    stripe_customer_id = subscription_data.get("customer")
    
    tenant_subscription = TenantSubscription.query.filter_by(
        stripe_customer_id=stripe_customer_id
    ).first()
    
    if tenant_subscription:
        tenant_subscription.stripe_subscription_id = subscription_data.get("id")
        tenant_subscription.status = "active"
        
        db.session.add(BillingEvent(
            tenant_id=tenant_subscription.tenant_id,
            event_type="subscription_created",
            description="Stripe subscription created",
            stripe_event_id=subscription_data.get("id")
        ))
        
        db.session.commit()


def _handle_subscription_updated(subscription_data):
    """Handle subscription updates."""
    stripe_subscription_id = subscription_data.get("id")
    
    tenant_subscription = TenantSubscription.query.filter_by(
        stripe_subscription_id=stripe_subscription_id
    ).first()
    
    if tenant_subscription:
        # Update status based on Stripe status
        stripe_status = subscription_data.get("status")
        if stripe_status == "active":
            tenant_subscription.status = "active"
        elif stripe_status == "canceled":
            tenant_subscription.status = "cancelled"
        elif stripe_status == "past_due":
            tenant_subscription.status = "suspended"
        
        db.session.add(BillingEvent(
            tenant_id=tenant_subscription.tenant_id,
            event_type="subscription_updated",
            description=f"Subscription status: {stripe_status}",
            stripe_event_id=subscription_data.get("id")
        ))
        
        db.session.commit()


def _handle_subscription_deleted(subscription_data):
    """Handle subscription cancellation."""
    stripe_subscription_id = subscription_data.get("id")
    
    tenant_subscription = TenantSubscription.query.filter_by(
        stripe_subscription_id=stripe_subscription_id
    ).first()
    
    if tenant_subscription:
        tenant_subscription.status = "cancelled"
        tenant_subscription.cancelled_at = db.func.now()
        
        db.session.add(BillingEvent(
            tenant_id=tenant_subscription.tenant_id,
            event_type="subscription_deleted",
            description="Subscription cancelled",
            stripe_event_id=subscription_data.get("id")
        ))
        
        db.session.commit()


def _handle_payment_succeeded(invoice):
    """Handle successful payment."""
    stripe_customer_id = invoice.get("customer")
    amount = invoice.get("amount_paid") / 100  # Convert from cents
    
    tenant_subscription = TenantSubscription.query.filter_by(
        stripe_customer_id=stripe_customer_id
    ).first()
    
    if tenant_subscription:
        tenant_subscription.last_payment_date = db.func.now()
        
        db.session.add(BillingEvent(
            tenant_id=tenant_subscription.tenant_id,
            event_type="payment_succeeded",
            amount=amount,
            currency="EUR",
            description=f"Payment of €{amount:.2f}",
            stripe_event_id=invoice.get("id")
        ))
        
        db.session.commit()


def _handle_payment_failed(invoice):
    """Handle failed payment."""
    from ...services.email_service import EmailService
    
    stripe_customer_id = invoice.get("customer")
    
    tenant_subscription = TenantSubscription.query.filter_by(
        stripe_customer_id=stripe_customer_id
    ).first()
    
    if tenant_subscription:
        # Suspend account after failed payment
        tenant_subscription.status = "suspended"
        
        db.session.add(BillingEvent(
            tenant_id=tenant_subscription.tenant_id,
            event_type="payment_failed",
            description="Payment failed",
            stripe_event_id=invoice.get("id")
        ))
        
        db.session.commit()
        
        # Send notification email
        tenant = Tenant.query.get(tenant_subscription.tenant_id)
        if tenant:
            admin_users = tenant.users.filter_by(status="active").all()
            for user in admin_users:
                if user.has_role("tenant_admin"):
                    EmailService.send_payment_failed_email(
                        user,
                        tenant_subscription.plan.name
                    )
