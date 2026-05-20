namespace AudelaMobileLight.Services;

public static class MobileLocalizer
{
    private const string LanguageKey = "mobile.lang";

    private static readonly Dictionary<string, Dictionary<string, string>> Translations = new(StringComparer.OrdinalIgnoreCase)
    {
        ["fr"] = new(StringComparer.OrdinalIgnoreCase)
        {
            ["lang.fr"] = "Francais",
            ["lang.en"] = "Anglais",
            ["lang.it"] = "Italien",
            ["config.title"] = "Configuration",
            ["config.native"] = "Mode natif actif: BI, Kanban, Finance et Learning utilisent des composants natifs.",
            ["config.account"] = "Mon compte tenant",
            ["config.oauth"] = "Seule exception web: redirection Google OAuth pendant l'authentification.",
            ["config.language"] = "Langue",
            ["tab.products"] = "Produits",
            ["tab.dashboard"] = "BI & AI",
            ["tab.kanban"] = "Kanban",
            ["tab.learning"] = "Learning",
            ["tab.finance"] = "Finance",
            ["tab.config"] = "Config",
            ["dashboard.aiSource"] = "Source des donnees AI",
            ["dashboard.aiAsk"] = "Demander a AI",
            ["dashboard.aiPlaceholder"] = "Ex: donne moi le resume finance",
            ["dashboard.source.auto"] = "Auto",
            ["dashboard.source.finance"] = "Finance",
            ["dashboard.source.kanban"] = "Kanban",
            ["dashboard.source.learning"] = "Learning",
            ["dashboard.source.dashboard"] = "Dashboard",
            ["kanban.details.title"] = "Details carte",
            ["kanban.details.owner"] = "Responsable",
            ["kanban.details.priority"] = "Priorite",
            ["kanban.details.due"] = "Echeance",
            ["finance.menu.dashboard"] = "Dashboard",
            ["finance.menu.transactions"] = "Transactions",
            ["finance.menu.quick"] = "Quick entry",
            ["finance.title"] = "Saisies finance natives",
            ["finance.subtitle"] = "Capture rapide des ecritures et mouvements depuis mobile.",
            ["finance.voiceFab"] = "Voix + entry",
            ["finance.voiceBtn"] = "Dictee vocale",
            ["finance.voiceUnavailable"] = "Reconnaissance vocale indisponible.",
            ["finance.voiceDenied"] = "Permission micro refusee.",
            ["finance.voiceError"] = "Echec reconnaissance vocale.",
            ["finance.error"] = "Erreur",
            ["finance.required"] = "Description et montant sont requis.",
            ["finance.invalidAmount"] = "Montant invalide.",
            ["finance.inputFail"] = "Saisie impossible",
            ["finance.success"] = "Succes",
        },
        ["en"] = new(StringComparer.OrdinalIgnoreCase)
        {
            ["lang.fr"] = "French",
            ["lang.en"] = "English",
            ["lang.it"] = "Italian",
            ["config.title"] = "Settings",
            ["config.native"] = "Native mode enabled: BI, Kanban, Finance and Learning use native components.",
            ["config.account"] = "Tenant account",
            ["config.oauth"] = "Only web exception: Google OAuth redirect during authentication.",
            ["config.language"] = "Language",
            ["tab.products"] = "Products",
            ["tab.dashboard"] = "BI & AI",
            ["tab.kanban"] = "Kanban",
            ["tab.learning"] = "Learning",
            ["tab.finance"] = "Finance",
            ["tab.config"] = "Settings",
            ["dashboard.aiSource"] = "AI data source",
            ["dashboard.aiAsk"] = "Ask AI",
            ["dashboard.aiPlaceholder"] = "Ex: give me the finance summary",
            ["dashboard.source.auto"] = "Auto",
            ["dashboard.source.finance"] = "Finance",
            ["dashboard.source.kanban"] = "Kanban",
            ["dashboard.source.learning"] = "Learning",
            ["dashboard.source.dashboard"] = "Dashboard",
            ["kanban.details.title"] = "Card details",
            ["kanban.details.owner"] = "Owner",
            ["kanban.details.priority"] = "Priority",
            ["kanban.details.due"] = "Due",
            ["finance.menu.dashboard"] = "Dashboard",
            ["finance.menu.transactions"] = "Transactions",
            ["finance.menu.quick"] = "Quick entry",
            ["finance.title"] = "Native finance entries",
            ["finance.subtitle"] = "Capture entries and cash movements quickly from mobile.",
            ["finance.voiceFab"] = "Voice + entry",
            ["finance.voiceBtn"] = "Voice dictation",
            ["finance.voiceUnavailable"] = "Voice recognition unavailable.",
            ["finance.voiceDenied"] = "Microphone permission denied.",
            ["finance.voiceError"] = "Voice recognition failed.",
            ["finance.error"] = "Error",
            ["finance.required"] = "Description and amount are required.",
            ["finance.invalidAmount"] = "Invalid amount.",
            ["finance.inputFail"] = "Cannot save entry",
            ["finance.success"] = "Success",
        },
        ["it"] = new(StringComparer.OrdinalIgnoreCase)
        {
            ["lang.fr"] = "Francese",
            ["lang.en"] = "Inglese",
            ["lang.it"] = "Italiano",
            ["config.title"] = "Configurazione",
            ["config.native"] = "Modalita nativa attiva: BI, Kanban, Finance e Learning usano componenti native.",
            ["config.account"] = "Account tenant",
            ["config.oauth"] = "Unica eccezione web: redirect Google OAuth durante l'autenticazione.",
            ["config.language"] = "Lingua",
            ["tab.products"] = "Prodotti",
            ["tab.dashboard"] = "BI & AI",
            ["tab.kanban"] = "Kanban",
            ["tab.learning"] = "Learning",
            ["tab.finance"] = "Finance",
            ["tab.config"] = "Config",
            ["dashboard.aiSource"] = "Fonte dati AI",
            ["dashboard.aiAsk"] = "Chiedi ad AI",
            ["dashboard.aiPlaceholder"] = "Es: dammi il riepilogo finance",
            ["dashboard.source.auto"] = "Auto",
            ["dashboard.source.finance"] = "Finance",
            ["dashboard.source.kanban"] = "Kanban",
            ["dashboard.source.learning"] = "Learning",
            ["dashboard.source.dashboard"] = "Dashboard",
            ["kanban.details.title"] = "Dettagli card",
            ["kanban.details.owner"] = "Responsabile",
            ["kanban.details.priority"] = "Priorita",
            ["kanban.details.due"] = "Scadenza",
            ["finance.menu.dashboard"] = "Dashboard",
            ["finance.menu.transactions"] = "Transazioni",
            ["finance.menu.quick"] = "Quick entry",
            ["finance.title"] = "Movimenti finance nativi",
            ["finance.subtitle"] = "Cattura rapida di movimenti e registrazioni dal mobile.",
            ["finance.voiceFab"] = "Voce + entry",
            ["finance.voiceBtn"] = "Dettatura vocale",
            ["finance.voiceUnavailable"] = "Riconoscimento vocale non disponibile.",
            ["finance.voiceDenied"] = "Permesso microfono negato.",
            ["finance.voiceError"] = "Riconoscimento vocale fallito.",
            ["finance.error"] = "Errore",
            ["finance.required"] = "Descrizione e importo sono obbligatori.",
            ["finance.invalidAmount"] = "Importo non valido.",
            ["finance.inputFail"] = "Impossibile salvare il movimento",
            ["finance.success"] = "Successo",
        },
    };

    public static event EventHandler? LanguageChanged;

    public static string CurrentLanguage { get; private set; } = Preferences.Default.Get(LanguageKey, "fr");

    static MobileLocalizer()
    {
        if (!Translations.ContainsKey(CurrentLanguage))
        {
            CurrentLanguage = "fr";
        }
    }

    public static IReadOnlyList<string> SupportedLanguages => ["fr", "en", "it"];

    public static void SetLanguage(string language)
    {
        var normalized = (language ?? "fr").Trim().ToLowerInvariant();
        if (!Translations.ContainsKey(normalized) || normalized == CurrentLanguage)
        {
            return;
        }

        CurrentLanguage = normalized;
        Preferences.Default.Set(LanguageKey, CurrentLanguage);
        LanguageChanged?.Invoke(null, EventArgs.Empty);
    }

    public static string T(string key)
    {
        if (Translations.TryGetValue(CurrentLanguage, out var localized) && localized.TryGetValue(key, out var value))
        {
            return value;
        }

        if (Translations["fr"].TryGetValue(key, out var fallback))
        {
            return fallback;
        }

        return key;
    }
}
