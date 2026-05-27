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
		BiTab.Title = MobileLocalizer.T("tab.dashboard");
		BiOverviewTab.Title = MobileLocalizer.T("bi.menu.overview");
		BiDashboardsTab.Title = MobileLocalizer.T("bi.menu.dashboards");
		BiQueriesTab.Title = MobileLocalizer.T("bi.menu.queries");
		BiChartsTab.Title = MobileLocalizer.T("bi.menu.charts");
		BiAiTab.Title = MobileLocalizer.T("bi.menu.ai");
		KanbanTab.Title = MobileLocalizer.T("tab.kanban");
		LearningTab.Title = MobileLocalizer.T("tab.learning");
		FinanceTab.Title = MobileLocalizer.T("tab.finance");
		ConfigTab.Title = MobileLocalizer.T("tab.config");
	}
}
