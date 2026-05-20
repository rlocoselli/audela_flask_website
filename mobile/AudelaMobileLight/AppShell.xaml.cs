using AudelaMobileLight.Services;

namespace AudelaMobileLight;

public partial class AppShell : Shell
{
	public AppShell()
	{
		InitializeComponent();
		MobileLocalizer.LanguageChanged += OnLanguageChanged;
		ApplyTranslations();
	}

	private void OnLanguageChanged(object? sender, EventArgs e)
	{
		ApplyTranslations();
	}

	private void ApplyTranslations()
	{
		ProductsTab.Title = MobileLocalizer.T("tab.products");
		DashboardTab.Title = MobileLocalizer.T("tab.dashboard");
		KanbanTab.Title = MobileLocalizer.T("tab.kanban");
		LearningTab.Title = MobileLocalizer.T("tab.learning");
		FinanceTab.Title = MobileLocalizer.T("tab.finance");
		ConfigTab.Title = MobileLocalizer.T("tab.config");
	}
}
