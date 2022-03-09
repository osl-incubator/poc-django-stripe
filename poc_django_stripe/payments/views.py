from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.http.response import (
    JsonResponse,
    HttpResponse,
    HttpResponseRedirect,
)
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_safe
from django.views.generic.base import TemplateView
from django.urls import reverse

import stripe

from djstripe import webhooks
from django.core.mail import send_mail

stripe.api_key = (
    settings.STRIPE_LIVE_SECRET_KEY
    if settings.STRIPE_LIVE_SECRET_KEY
    else settings.STRIPE_TEST_SECRET_KEY
)


def _get_payments_url(request, view_name="payments:main"):
    return request.build_absolute_uri(reverse(view_name))


class CheckoutPageView(LoginRequiredMixin, TemplateView):
    template_name = "payments/checkout.html"


class CheckoutSuccessPageView(LoginRequiredMixin, TemplateView):
    template_name = "payments/checkout-success.html"


class CheckoutCancelledPageView(LoginRequiredMixin, TemplateView):
    template_name = "payments/checkout-cancelled.html"


class CustomerPortalPageView(LoginRequiredMixin, TemplateView):
    template_name = "payments/customer-portal.html"


@login_required
@csrf_exempt
def stripe_config(request):
    if request.method == "GET":
        stripe_config = {"publicKey": settings.STRIPE_PUBLISHABLE_KEY}
        return JsonResponse(stripe_config, safe=False)


# STRIPE


@login_required
@csrf_exempt
def stripe_checkout(request):
    PAYMENTS_URL = _get_payments_url(request)

    if request.method == "GET":
        try:
            # Create new Checkout Session for the order
            # Other optional params include:
            # [billing_address_collection] - to display billing address
            #   details on the page
            # [customer] - if you have an existing Stripe Customer ID
            # [payment_intent_data] - capture the payment later
            # [customer_email] - prefill the email input in the form
            # For full details see:
            #   https://stripe.com/docs/api/checkout/sessions/create

            # ?session_id={CHECKOUT_SESSION_ID} means the redirect
            # will have the session ID set as a query param
            checkout_session = stripe.checkout.Session.create(
                # new
                client_reference_id=request.user.id
                if request.user.is_authenticated
                else None,
                success_url=PAYMENTS_URL
                + "checkout-success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=PAYMENTS_URL + "checkout-cancelled/",
                payment_method_types=["card"],
                mode="payment",
                line_items=[
                    {
                        "name": "T-shirt",
                        "quantity": 1,
                        "currency": "usd",
                        "amount": "2000",
                    }
                ],
            )
            return JsonResponse({"sessionId": checkout_session["id"]})
        except Exception as e:
            return JsonResponse({"error": str(e)})


""" @csrf_exempt
def stripe_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
    payload = request.body
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        print("Payment was successful.")
        # TODO: run some custom code here

    return HttpResponse(status=200) """


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def stripe_customer_portal(request):
    customer = Customer.objects.get(subscriber=request.user)

    PAYMENTS_URL = _get_payments_url(
        request, view_name="payments:customer-portal"
    )

    # Authenticate your user.
    session = stripe.billing_portal.Session.create(
        customer=customer.id,
        return_url=f"{PAYMENTS_URL}",
    )
    return HttpResponseRedirect(session.url)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def stripe_customer_portal(request):
    stripe.Account.create(
        country="US",
        type="express",
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        business_type="individual",
        business_profile={"url": "https://example.com"},
    )


# DJ Stripe


@webhooks.handler("customer.deleted")
def customer_deleted_event_listener(event, **kwargs):
    send_mail(
        "Subscription Deleted",
        "See ya! 👋",
        "from@example.com",
        ["to@example.com"],
        fail_silently=False,
    )
