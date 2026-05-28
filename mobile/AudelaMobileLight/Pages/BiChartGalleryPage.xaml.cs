using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;
using Microsoft.Maui.Controls.Shapes;
using Microsoft.Maui.Layouts;

namespace AudelaMobileLight.Pages;

public class BiChartGalleryPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private readonly Picker _dashboardPicker;
    private readonly FlexLayout _filterChipsLayout;
    private readonly CollectionView _cardsView;
    private string _activeFilter = "all";

    private static readonly Dictionary<string, (Color CardBg, Color Strip, Color TagBg, Color TagText, string Emoji, string Label)> VizStyles = new(StringComparer.OrdinalIgnoreCase)
    {
        ["kpi"]   = (Color.FromArgb("#F0F7FF"), Color.FromArgb("#1E4FBB"), Color.FromArgb("#CFE3FF"), Color.FromArgb("#0A2F8A"), "🔢", "KPI"),
        ["bar"]   = (Color.FromArgb("#FFF8EF"), Color.FromArgb("#D4620A"), Color.FromArgb("#FDECD9"), Color.FromArgb("#8A3D0A"), "📊", "Bar"),
        ["line"]  = (Color.FromArgb("#F0FBF4"), Color.FromArgb("#1A7A3A"), Color.FromArgb("#C9F0D8"), Color.FromArgb("#0D5227"), "📈", "Line"),
        ["pie"]   = (Color.FromArgb("#FAF0FF"), Color.FromArgb("#7C29B8"), Color.FromArgb("#EDD9FF"), Color.FromArgb("#50157A"), "🥧", "Pie"),
        ["table"] = (Color.FromArgb("#F6F8FB"), Color.FromArgb("#4A6A8A"), Color.FromArgb("#DCE9F5"), Color.FromArgb("#253C52"), "📋", "Table"),
        ["area"] = (Color.FromArgb("#ECFBFF"), Color.FromArgb("#118AA5"), Color.FromArgb("#D6F2FA"), Color.FromArgb("#0A5A70"), "🌊", "Area"),
        ["scatter"] = (Color.FromArgb("#F6F5FF"), Color.FromArgb("#4C49BE"), Color.FromArgb("#E4E2FF"), Color.FromArgb("#2D2A8A"), "🔷", "Scatter"),
        ["donut"] = (Color.FromArgb("#FFF3F7"), Color.FromArgb("#C63F7B"), Color.FromArgb("#FFD9EB"), Color.FromArgb("#8A1F52"), "🍩", "Donut"),
    };

    public ObservableCollection<MobileBiDashboardSummary> Dashboards { get; } = [];
    public ObservableCollection<MobileBiDashboardCard> AllCards { get; } = [];
    public ObservableCollection<MobileBiDashboardCard> Cards { get; } = [];
    public MobileBiDashboardSummary? SelectedDashboard { get; set; }
    public bool IsLoading { get; private set; }

    public BiChartGalleryPage()
    {
        Title = "Chart Gallery";

        _dashboardPicker = new Picker
        {
            Title = "Select dashboard",
            ItemDisplayBinding = new Binding(nameof(MobileBiDashboardSummary.Name)),
            TextColor = Colors.White,
            TitleColor = Color.FromArgb("#C7DAFF"),
        };
        _dashboardPicker.SetBinding(Picker.ItemsSourceProperty, nameof(Dashboards));
        _dashboardPicker.SetBinding(Picker.SelectedItemProperty, nameof(SelectedDashboard));
        _dashboardPicker.SelectedIndexChanged += OnDashboardChanged;

        // Filter chips row
        _filterChipsLayout = new FlexLayout
        {
            Wrap = FlexWrap.Wrap,
            Direction = FlexDirection.Row,
            JustifyContent = FlexJustify.Start,
            AlignItems = FlexAlignItems.Center,
        };
        BuildFilterChips();

        _cardsView = new CollectionView();
        _cardsView.SetBinding(ItemsView.ItemsSourceProperty, new Binding(nameof(Cards), source: this));
        _cardsView.ItemTemplate = new DataTemplate(BuildCardTemplate);

        var emptyLabel = new Label
        {
            Text = "No charts found.\nChoose another dashboard or filter.",
            FontSize = 13,
            TextColor = Color.FromArgb("#6A7FA0"),
            HorizontalTextAlignment = TextAlignment.Center,
            Margin = new Thickness(0, 24),
        };
        _cardsView.EmptyView = emptyLabel;

        var loading = new ActivityIndicator();
        loading.SetBinding(ActivityIndicator.IsVisibleProperty, nameof(IsLoading));
        loading.SetBinding(ActivityIndicator.IsRunningProperty, nameof(IsLoading));

        Content = new ScrollView
        {
            BackgroundColor = Color.FromArgb("#EEF3FB"),
            Content = new VerticalStackLayout
            {
                Padding = 14,
                Spacing = 12,
                Children =
                {
                    // Header
                    new Border
                    {
                        StrokeThickness = 0,
                        Padding = 14,
                        StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(20) },
                        Background = new LinearGradientBrush(
                            new GradientStopCollection
                            {
                                new GradientStop(Color.FromArgb("#0A255B"), 0.0f),
                                new GradientStop(Color.FromArgb("#1E4FBB"), 1.0f),
                            },
                            new Point(0, 0),
                            new Point(1, 1)),
                        Content = new VerticalStackLayout
                        {
                            Spacing = 8,
                            Children =
                            {
                                new Label { Text = "📊 Chart Gallery", FontSize = 22, FontAttributes = FontAttributes.Bold, TextColor = Colors.White },
                                new Label { Text = "Mobile overview of web charts: KPI, bar, line, area, scatter, pie/donut and table.", FontSize = 12, TextColor = Color.FromArgb("#C7DAFF") },
                                new Label { Text = "Tip: pick a dashboard first, then filter by type chips below.", FontSize = 11, TextColor = Color.FromArgb("#DAE6FF") },
                                _dashboardPicker,
                            },
                        },
                    },
                    new Border
                    {
                        Stroke = Color.FromArgb("#D8E5F5"),
                        StrokeThickness = 1,
                        BackgroundColor = Color.FromArgb("#F8FBFF"),
                        Padding = new Thickness(10, 9),
                        StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(12) },
                        Content = new Label
                        {
                            FontSize = 11,
                            TextColor = Color.FromArgb("#385A7A"),
                            Text = "How to read this page: type badge shows render mode. If a web card is Area/Scatter/Donut, mobile keeps that label and renders the closest lightweight view.",
                            LineBreakMode = LineBreakMode.WordWrap,
                        },
                    },
                    // Filter chips
                    new Border
                    {
                        Stroke = Color.FromArgb("#DCE7F5"),
                        StrokeThickness = 1,
                        BackgroundColor = Colors.White,
                        Padding = new Thickness(10, 8),
                        StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(14) },
                        Content = _filterChipsLayout,
                    },
                    _cardsView,
                    loading,
                },
            },
        };

        BindingContext = this;
    }

    private void BuildFilterChips()
    {
        _filterChipsLayout.Children.Clear();

        var filters = new[]
        {
            ("all", "All", "⬛"),
            ("kpi", "KPI", "🔢"),
            ("bar", "Bar", "📊"),
            ("line", "Line", "📈"),
            ("area", "Area", "🌊"),
            ("scatter", "Scatter", "🔷"),
            ("pie", "Pie", "🥧"),
            ("donut", "Donut", "🍩"),
            ("table", "Table", "📋"),
        };

        foreach (var (key, label, emoji) in filters)
        {
            var isActive = _activeFilter == key;
            var chip = new Border
            {
                StrokeThickness = isActive ? 0 : 1,
                Stroke = isActive ? null : Color.FromArgb("#C5D8F0"),
                BackgroundColor = isActive ? Color.FromArgb("#1E4FBB") : Colors.White,
                Padding = new Thickness(12, 6),
                Margin = new Thickness(3, 3),
                StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(20) },
                Content = new Label
                {
                    Text = $"{emoji} {label}",
                    FontSize = 12,
                    FontAttributes = isActive ? FontAttributes.Bold : FontAttributes.None,
                    TextColor = isActive ? Colors.White : Color.FromArgb("#2A4A6A"),
                },
            };

            var chipKey = key;
            chip.GestureRecognizers.Add(new TapGestureRecognizer
            {
                Command = new Command(() =>
                {
                    _activeFilter = chipKey;
                    BuildFilterChips();
                    ApplyFilter();
                }),
            });

            _filterChipsLayout.Children.Add(chip);
        }
    }

    private void ApplyFilter()
    {
        Cards.Clear();
        var source = _activeFilter == "all"
            ? AllCards
            : AllCards.Where(c =>
                string.Equals(c.VizStyleKey, _activeFilter, StringComparison.OrdinalIgnoreCase)
                || (_activeFilter == "line" && string.Equals(c.VizTypeNormalized, "line", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(c.VizStyleKey, "area", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(c.VizStyleKey, "scatter", StringComparison.OrdinalIgnoreCase))
                || (_activeFilter == "pie" && string.Equals(c.VizTypeNormalized, "pie", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(c.VizStyleKey, "donut", StringComparison.OrdinalIgnoreCase)));

        foreach (var card in source)
        {
            Cards.Add(card);
        }
    }

    private View BuildCardTemplate()
    {
        // VizType badge
        var typeLabel = new Label { FontSize = 10, FontAttributes = FontAttributes.Bold };
        typeLabel.SetBinding(Label.TextProperty, new Binding(nameof(MobileBiDashboardCard.VizStyleKey),
            converter: new FuncConverter<string, string>(t => VizStyles.TryGetValue(t ?? "table", out var s) ? $"{s.Emoji} {s.Label}" : t ?? "table")));

        var typeBadge = new Border
        {
            Padding = new Thickness(8, 3),
            StrokeThickness = 0,
            StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(10) },
            Content = typeLabel,
        };
        typeBadge.SetBinding(Border.BackgroundColorProperty, new Binding(nameof(MobileBiDashboardCard.VizStyleKey),
            converter: new FuncConverter<string, Color>(t => VizStyles.TryGetValue(t ?? "table", out var s) ? s.TagBg : Colors.LightGray)));
        typeLabel.SetBinding(Label.TextColorProperty, new Binding(nameof(MobileBiDashboardCard.VizStyleKey),
            converter: new FuncConverter<string, Color>(t => VizStyles.TryGetValue(t ?? "table", out var s) ? s.TagText : Colors.DarkGray)));

        var title = new Label { FontAttributes = FontAttributes.Bold, TextColor = Color.FromArgb("#163252"), FontSize = 15 };
        title.SetBinding(Label.TextProperty, nameof(MobileBiDashboardCard.Title));

        var headerRow = new Grid
        {
            ColumnDefinitions = new ColumnDefinitionCollection
            {
                new ColumnDefinition(GridLength.Star),
                new ColumnDefinition(GridLength.Auto),
            },
            ColumnSpacing = 8,
            Children = { title, typeBadge },
        };
        Grid.SetColumn(typeBadge, 1);

        var source = new Label { FontSize = 11, TextColor = Color.FromArgb("#5E7392") };
        source.SetBinding(Label.TextProperty, new Binding(nameof(MobileBiDashboardCard.SourceName),
            stringFormat: "⛁  {0}"));

        var variantHint = new Label { FontSize = 11, TextColor = Color.FromArgb("#4D6E95") };
        variantHint.SetBinding(Label.TextProperty, new Binding(nameof(MobileBiDashboardCard.DisplayVizLabel),
            stringFormat: "Render: {0}"));

        // KPI: big primary value
        var kpiValue = new Label
        {
            FontSize = 32,
            FontAttributes = FontAttributes.Bold,
            TextColor = Color.FromArgb("#0A2F8A"),
            HorizontalTextAlignment = TextAlignment.Center,
            Margin = new Thickness(0, 4),
        };
        kpiValue.SetBinding(Label.TextProperty, nameof(MobileBiDashboardCard.PrimaryValue));
        kpiValue.SetBinding(Label.IsVisibleProperty, nameof(MobileBiDashboardCard.IsKpi));

        // Secondary label (trend / secondary value)
        var secondaryLabel = new Label
        {
            FontSize = 12,
            TextColor = Color.FromArgb("#6A7FA0"),
            MaxLines = 3,
            LineBreakMode = LineBreakMode.TailTruncation,
        };
        secondaryLabel.SetBinding(Label.TextProperty, nameof(MobileBiDashboardCard.TrendLabel));

        // Mini bar preview for bar/line types
        var miniBar = new VerticalStackLayout { Spacing = 3, Margin = new Thickness(0, 6, 0, 0) };
        miniBar.SetBinding(VisualElement.IsVisibleProperty, new Binding(nameof(MobileBiDashboardCard.IsBar)));

        var miniBarPoints = new Label
        {
            FontSize = 10,
            TextColor = Color.FromArgb("#5E7392"),
            FontFamily = "Courier",
        };
        miniBarPoints.SetBinding(Label.TextProperty, new Binding(nameof(MobileBiDashboardCard.Points),
            converter: new FuncConverter<List<MobileBiPoint>, string>(BuildMiniBar)));
        miniBar.Children.Add(miniBarPoints);

        // Table preview rows
        var tablePreview = new VerticalStackLayout { Spacing = 2, Margin = new Thickness(0, 4, 0, 0) };
        tablePreview.SetBinding(VisualElement.IsVisibleProperty, nameof(MobileBiDashboardCard.IsTable));

        var previewText = new Label
        {
            FontSize = 11,
            TextColor = Color.FromArgb("#4C6588"),
            LineBreakMode = LineBreakMode.TailTruncation,
            MaxLines = 4,
        };
        previewText.SetBinding(Label.TextProperty, new Binding(nameof(MobileBiDashboardCard.PreviewRows),
            converter: new FuncConverter<List<string>, string>(rows =>
                rows is null || rows.Count == 0 ? "— No preview data —"
                : string.Join("\n", rows.Take(4).Select(r => "▸  " + r)))));
        tablePreview.Children.Add(previewText);

        var card = new Border
        {
            Padding = 12,
            Margin = new Thickness(0, 0, 0, 10),
            StrokeThickness = 0,
            StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(16) },
        };
        card.SetBinding(Border.BackgroundColorProperty, new Binding(nameof(MobileBiDashboardCard.VizStyleKey),
            converter: new FuncConverter<string, Color>(t => VizStyles.TryGetValue(t ?? "table", out var s) ? s.CardBg : Colors.White)));

        // Left accent strip via BoxView in Grid
        var strip = new BoxView { WidthRequest = 5 };
        strip.SetBinding(BoxView.ColorProperty, new Binding(nameof(MobileBiDashboardCard.VizStyleKey),
            converter: new FuncConverter<string, Color>(t => VizStyles.TryGetValue(t ?? "table", out var s) ? s.Strip : Colors.Gray)));

        var contentStack = new VerticalStackLayout
        {
            Spacing = 6,
            Children = { headerRow, source, variantHint, kpiValue, miniBar, tablePreview, secondaryLabel },
        };

        var innerGrid = new Grid
        {
            ColumnDefinitions = new ColumnDefinitionCollection
            {
                new ColumnDefinition(new GridLength(6)),
                new ColumnDefinition(GridLength.Star),
            },
            ColumnSpacing = 10,
            Children = { strip, contentStack },
        };
        Grid.SetColumn(contentStack, 1);

        card.Content = innerGrid;
        return card;
    }

    private static string BuildMiniBar(List<MobileBiPoint>? points)
    {
        if (points is null || points.Count == 0)
        {
            return "No data";
        }

        var max = points.Max(p => Math.Abs(p.Y));
        if (max == 0) max = 1;

        var result = new System.Text.StringBuilder();
        foreach (var p in points.Take(6))
        {
            var barLen = (int)Math.Round(Math.Abs(p.Y) / max * 12);
            var bar = new string('█', Math.Max(1, barLen));
            result.AppendLine($"{(p.X.Length > 6 ? p.X[..6] : p.X),6} {bar} {p.Y:0.#}");
        }

        return result.ToString().TrimEnd();
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await EnsureDashboardsLoadedAsync();
    }

    private async Task EnsureDashboardsLoadedAsync()
    {
        if (Dashboards.Count > 0)
        {
            return;
        }

        var dashboards = await _service.GetBiDashboardsAsync(CancellationToken.None);
        Dashboards.Clear();
        foreach (var dashboard in dashboards)
        {
            Dashboards.Add(dashboard);
        }

        SelectedDashboard = Dashboards.FirstOrDefault();
        OnPropertyChanged(nameof(SelectedDashboard));

        if (SelectedDashboard is not null)
        {
            await LoadCardsAsync(SelectedDashboard);
        }
    }

    private async void OnDashboardChanged(object? sender, EventArgs e)
    {
        if (_dashboardPicker.SelectedItem is MobileBiDashboardSummary dashboard)
        {
            SelectedDashboard = dashboard;
            OnPropertyChanged(nameof(SelectedDashboard));
            await LoadCardsAsync(dashboard);
        }
    }

    private async Task LoadCardsAsync(MobileBiDashboardSummary dashboard)
    {
        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var detail = await _service.GetBiDashboardDetailAsync(dashboard.Id, CancellationToken.None);
            AllCards.Clear();
            Cards.Clear();

            if (detail is not null)
            {
                foreach (var card in detail.Cards)
                {
                    AllCards.Add(card);
                }
            }

            _activeFilter = "all";
            BuildFilterChips();
            ApplyFilter();
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }
}

// Inline converter helper
internal sealed class FuncConverter<TIn, TOut> : IValueConverter
{
    private readonly Func<TIn?, TOut> _func;
    public FuncConverter(Func<TIn?, TOut> func) => _func = func;
    public object? Convert(object? value, Type targetType, object? parameter, System.Globalization.CultureInfo culture)
        => _func(value is TIn t ? t : default);
    public object? ConvertBack(object? value, Type targetType, object? parameter, System.Globalization.CultureInfo culture)
        => throw new NotSupportedException();
}
