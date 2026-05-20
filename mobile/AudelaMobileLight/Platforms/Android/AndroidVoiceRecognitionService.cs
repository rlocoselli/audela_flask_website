#if ANDROID
using AudelaMobileLight.Services;
using Bundle = global::Android.OS.Bundle;
using GeneratedEnumAttribute = global::Android.Runtime.GeneratedEnumAttribute;
using Intent = global::Android.Content.Intent;
using IRecognitionListener = global::Android.Speech.IRecognitionListener;
using RecognizerIntent = global::Android.Speech.RecognizerIntent;
using SpeechRecognizer = global::Android.Speech.SpeechRecognizer;
using SpeechRecognizerError = global::Android.Speech.SpeechRecognizerError;

namespace AudelaMobileLight.Platforms.Android;

public sealed class AndroidVoiceRecognitionService : global::Java.Lang.Object, IVoiceRecognitionService
{
    public async Task<(bool Ok, string Text, string Message)> RecognizeAsync(CancellationToken cancellationToken)
    {
        var hasFeature = Platform.CurrentActivity?.PackageManager?.HasSystemFeature(global::Android.Content.PM.PackageManager.FeatureMicrophone) ?? false;
        if (!hasFeature)
        {
            return (false, string.Empty, MobileLocalizer.T("finance.voiceUnavailable"));
        }

        var permission = await Permissions.CheckStatusAsync<Permissions.Microphone>();
        if (permission != PermissionStatus.Granted)
        {
            permission = await Permissions.RequestAsync<Permissions.Microphone>();
            if (permission != PermissionStatus.Granted)
            {
                return (false, string.Empty, MobileLocalizer.T("finance.voiceDenied"));
            }
        }

        var activity = Platform.CurrentActivity;
        if (activity is null)
        {
            return (false, string.Empty, MobileLocalizer.T("finance.voiceUnavailable"));
        }

        var tcs = new TaskCompletionSource<(bool Ok, string Text, string Message)>();
        var listener = new RecognitionListenerImpl(tcs);
        using var recognizer = SpeechRecognizer.CreateSpeechRecognizer(activity);
        if (recognizer is null)
        {
            return (false, string.Empty, MobileLocalizer.T("finance.voiceUnavailable"));
        }
        recognizer.SetRecognitionListener(listener);

        using var intent = new Intent(RecognizerIntent.ActionRecognizeSpeech);
        intent.PutExtra(RecognizerIntent.ExtraLanguageModel, RecognizerIntent.LanguageModelFreeForm);
        intent.PutExtra(RecognizerIntent.ExtraCallingPackage, activity.PackageName);
        intent.PutExtra(RecognizerIntent.ExtraPartialResults, false);
        intent.PutExtra(RecognizerIntent.ExtraLanguage, global::Java.Util.Locale.Default);

        using var _ = cancellationToken.Register(() => tcs.TrySetResult((false, string.Empty, MobileLocalizer.T("finance.voiceError"))));

        recognizer.StartListening(intent);
        var result = await tcs.Task;
        recognizer.StopListening();
        recognizer.Cancel();

        return result;
    }

    private sealed class RecognitionListenerImpl(TaskCompletionSource<(bool Ok, string Text, string Message)> tcs) : global::Java.Lang.Object, IRecognitionListener
    {
        public void OnReadyForSpeech(Bundle? @params) { }

        public void OnBeginningOfSpeech() { }

        public void OnRmsChanged(float rmsdB) { }

        public void OnBufferReceived(byte[]? buffer) { }

        public void OnEndOfSpeech() { }

        public void OnError([GeneratedEnumAttribute] SpeechRecognizerError error)
        {
            tcs.TrySetResult((false, string.Empty, MobileLocalizer.T("finance.voiceError")));
        }

        public void OnResults(Bundle? results)
        {
            var texts = results?.GetStringArrayList(SpeechRecognizer.ResultsRecognition);
            var best = texts?.FirstOrDefault()?.Trim() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(best))
            {
                tcs.TrySetResult((false, string.Empty, MobileLocalizer.T("finance.voiceError")));
                return;
            }

            tcs.TrySetResult((true, best, string.Empty));
        }

        public void OnPartialResults(Bundle? partialResults) { }

        public void OnEvent(int eventType, Bundle? @params) { }
    }
}
#endif
