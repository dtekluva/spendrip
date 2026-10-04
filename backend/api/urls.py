from django.urls import path

from . import app_views as app
from . import auth_views as auth
from . import system_views as system
from seasons.views import CurrentSeason

urlpatterns = [
    # system
    path("health", system.Health.as_view()),
    path("season", CurrentSeason.as_view()),
    path("cron/tick", system.CronTick.as_view()),
    path("webhooks/liberty", system.LibertyWebhook.as_view()),
    path("webhooks/paystack", system.paystack_webhook),
    path("waitlist", system.Waitlist.as_view()),
    path("dev/top-up", system.DevTopUp.as_view()),
    path("dev/tick", system.DevTick.as_view()),
    # who am I
    path("me", auth.Me.as_view()),
    path("me/settings", auth.MeUpdate.as_view()),
    # sign-up: email → code → name → PIN → Face ID
    path("signup/start", auth.SignupStart.as_view()),
    path("signup/otp/resend", auth.SignupResendOtp.as_view()),
    path("signup/otp/verify", auth.SignupVerifyOtp.as_view()),
    path("signup/name", auth.SignupName.as_view()),
    # verify identity, later in the app: ID photo → three face angles
    path("kyc/document", auth.KycDocument.as_view()),
    path("kyc/liveness/start", auth.KycLivenessStart.as_view()),
    path("kyc/liveness", auth.KycLiveness.as_view()),
    # PIN, lock, sign-in, Face ID
    path("auth/pin", auth.SetPin.as_view()),
    path("auth/pin/change", auth.ChangePin.as_view()),
    path("auth/unlock", auth.Unlock.as_view()),
    path("auth/lock", auth.Lock.as_view()),
    path("auth/signin/start", auth.SigninStart.as_view()),
    path("auth/signin/verify", auth.SigninVerify.as_view()),
    path("auth/signout", auth.Signout.as_view()),
    path("auth/passkey/register/options", auth.PasskeyRegisterOptions.as_view()),
    path("auth/passkey/register/verify", auth.PasskeyRegisterVerify.as_view()),
    path("auth/passkey/unlock/options", auth.PasskeyUnlockOptions.as_view()),
    path("auth/passkey/unlock/verify", auth.PasskeyUnlockVerify.as_view()),
    path("auth/passkey", auth.PasskeyRemove.as_view()),
    # app
    path("summary", app.Summary.as_view()),
    path("banks", app.Banks.as_view()),
    path("recipients", app.Recipients.as_view()),
    path("recipients/lookup", app.RecipientLookup.as_view()),
    path("recipients/<int:pk>", app.RecipientDetail.as_view()),
    path("plans", app.Plans.as_view()),
    path("plans/preview", app.PlanPreview.as_view()),
    path("plans/<int:pk>", app.PlanDetail.as_view()),
    path("calendar", app.Calendar.as_view()),
    path("funding/card/quote", app.CardQuote.as_view()),
    path("funding/card/start", app.CardStart.as_view()),
    path("funding/card/verify", app.CardVerify.as_view()),
    path("funding/card/charge", app.SavedCardTopUp.as_view()),
    path("cards", app.Cards.as_view()),
    path("cards/<int:pk>", app.CardDetail.as_view()),
    path("activity", app.Activity.as_view()),
    path("payouts/<uuid:pk>/retry", app.PayoutRetry.as_view()),
]
