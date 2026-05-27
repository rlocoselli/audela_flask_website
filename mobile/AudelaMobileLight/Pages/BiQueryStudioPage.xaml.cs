using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;
using Microsoft.Maui.Controls.Shapes;

namespace AudelaMobileLight.Pages;

public class BiQueryStudioPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private readonly string _defaultSourceToken;
    private readonly Picker _dataSourcePicker;
    private readonly Editor _sqlEditor;
    private readonly Label _aiModelLabel;
    private readonly Label _nlModeLabel;
    private readonly Switch _nlSwitch;
    private string _aiModelName = string.Empty;

    public ObservableCollection<MobileBiDataSource> BiDataSources { get; } = [];
    public ObservableCollection<string> ResultRows { get; } = [];

    public MobileBiDataSource? SelectedBiDataSource { get; set; }
    public string ColumnsPreview { get; private set; } = "-";
    public string QueryStatus { get; private set; } = "Ready";
    public bool IsLoading { get; private set; }
    public bool UseNaturalLanguage { get; set; }

    public BiQueryStudioPage(string defaultSourceToken = "")
    {
        _defaultSourceToken = defaultSourceToken;

        Title = "BI Query Studio";
        _dataSourcePicker = new Picker
        {
            ItemDisplayBinding = new Binding(nameof(MobileBiDataSource.DisplayName)),
            TextColor = Colors.White,
            TitleColor = Color.FromArgb("#C7DAFF"),
        };
        _dataSourcePicker.SetBinding(Picker.ItemsSourceProperty, nameof(BiDataSources));
        _dataSourcePicker.SetBinding(Picker.SelectedItemProperty, nameof(SelectedBiDataSource));

        _sqlEditor = new Editor
        {
            HeightRequest = 140,
            Placeholder = "SELECT * FROM your_table LIMIT 20",
            AutoSize = EditorAutoSizeOption.TextChanges,
            Text = "SELECT 1 AS value",
            TextColor = Colors.White,
            PlaceholderColor = Color.FromArgb("#8FADD4"),
            BackgroundColor = Color.FromArgb("#0F2A55"),
        };

        _aiModelLabel = new Label
        {
            Text = "",
            FontSize = 11,
            TextColor = Color.FromArgb("#8FD3FF"),
        };

        _nlModeLabel = new Label
        {
            Text = "Natural language (AI)",
            FontSize = 12,
            TextColor = Color.FromArgb("#C7DAFF"),
            VerticalTextAlignment = TextAlignment.Center,
        };

        _nlSwitch = new Switch
        {
            IsToggled = false,
            OnColor = Color.FromArgb("#3B82F6"),
            ThumbColor = Colors.White,
        };
        _nlSwitch.Toggled += OnNlSwitchToggled;

        var runButton = new Button
        {
            Text = "Run query",
            BackgroundColor = Color.FromArgb("#1F58CC"),
            CornerRadius = 14,
            Padding = new Thickness(12, 7),
            FontAttributes = FontAttributes.Bold,
            FontSize = 13,
            MinimumHeightRequest = 36,
            MinimumWidthRequest = 36,
        };
        runButton.Clicked += OnRunQueryClicked;

        var statusLabel = new Label
        {
            FontSize = 12,
            TextColor = Color.FromArgb("#4B6789"),
            VerticalTextAlignment = TextAlignment.Center,
        };
        statusLabel.SetBinding(Label.TextProperty, nameof(QueryStatus));

        var columnsLabel = new Label
        {
            FontSize = 12,
            TextColor = Color.FromArgb("#355E84"),
        };
        columnsLabel.SetBinding(Label.TextProperty, nameof(ColumnsPreview));

        var resultsView = new CollectionView
        {
            HeightRequest = 320,
        };
        resultsView.SetBinding(ItemsView.ItemsSourceProperty, nameof(ResultRows));
        resultsView.ItemTemplate = new DataTemplate(() =>
        {
            var label = new Label
            {
                FontSize = 12,
                TextColor = Color.FromArgb("#254B70"),
                MaxLines = 2,
                LineBreakMode = LineBreakMode.TailTruncation,
            };
            label.SetBinding(Label.TextProperty, ".");

            return new Border
            {
                Stroke = Color.FromArgb("#DCE7F7"),
                StrokeThickness = 1,
                BackgroundColor = Color.FromArgb("#F8FBFF"),
                Padding = 8,
                Margin = new Thickness(0, 0, 0, 6),
                StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(10) },
                Content = label,
            };
        });

        var activity = new ActivityIndicator();
        activity.SetBinding(ActivityIndicator.IsVisibleProperty, nameof(IsLoading));
        activity.SetBinding(ActivityIndicator.IsRunningProperty, nameof(IsLoading));

        var runRow = new Grid
        {
            ColumnDefinitions = new ColumnDefinitionCollection
            {
                new ColumnDefinition(GridLength.Auto),
                new ColumnDefinition(GridLength.Star),
            },
            ColumnSpacing = 8,
            Children = { runButton, statusLabel },
        };
        Grid.SetColumn(statusLabel, 1);

        Content = new ScrollView
        {
            BackgroundColor = Color.FromArgb("#EEF3FB"),
            Content = new VerticalStackLayout
            {
                Padding = 14,
                Spacing = 12,
                Children =
                {
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
                                new Label { Text = "Query Studio", FontSize = 22, FontAttributes = FontAttributes.Bold, TextColor = Colors.White },
                                new Label { Text = "Execute read-only SQL queries against BI datasources.", FontSize = 12, TextColor = Color.FromArgb("#C7DAFF") },
                                _aiModelLabel,
                                _dataSourcePicker,
                                new Border
                                {
                                    StrokeThickness = 0,
                                    BackgroundColor = Color.FromArgb("#0F327A"),
                                    Padding = new Thickness(8, 4),
                                    StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(10) },
                                    Content = new HorizontalStackLayout
                                    {
                                        Spacing = 10,
                                        VerticalOptions = LayoutOptions.Center,
                                        Children =
                                        {
                                            new Label { Text = "Readonly mode", FontSize = 11, TextColor = Color.FromArgb("#D7E4FF"), VerticalTextAlignment = TextAlignment.Center, HorizontalOptions = LayoutOptions.StartAndExpand },
                                            _nlModeLabel,
                                            _nlSwitch,
                                        },
                                    },
                                },
                                _sqlEditor,
                                runRow,
                            },
                        },
                    },
                    new Border
                    {
                        Stroke = Color.FromArgb("#DCE7F7"),
                        StrokeThickness = 1,
                        BackgroundColor = Colors.White,
                        Padding = 12,
                        StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(16) },
                        Content = new VerticalStackLayout
                        {
                            Spacing = 8,
                            Children =
                            {
                                new Label { Text = "Columns", FontAttributes = FontAttributes.Bold, TextColor = Color.FromArgb("#17314A") },
                                columnsLabel,
                                new Label { Text = "Rows", FontAttributes = FontAttributes.Bold, TextColor = Color.FromArgb("#17314A") },
                                resultsView,
                            },
                        },
                    },
                    activity,
                },
            },
        };

        BindingContext = this;
    }

    private static T? FindVisualChild<T>(Element parent, Func<T, bool> predicate) where T : Element
    {
        if (parent is null) return null;
        if (parent is T t && predicate(t)) return t;
        if (parent is Layout layout)
        {
            foreach (var child in layout.Children)
            {
                if (child is not Element childElement)
                {
                    continue;
                }

                var result = FindVisualChild(childElement, predicate);
                if (result is not null) return result;
            }
        }
        return null;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await EnsureDataSourcesLoadedAsync();
    }

    private async Task EnsureDataSourcesLoadedAsync()
    {
        if (BiDataSources.Count > 0)
        {
            return;
        }

        var rows = await _service.GetBiDataSourcesAsync(CancellationToken.None);
        BiDataSources.Clear();
        foreach (var row in rows)
        {
            BiDataSources.Add(row);
        }

        var selected = BiDataSources.FirstOrDefault(x => string.Equals(x.Token, _defaultSourceToken, StringComparison.OrdinalIgnoreCase));
        SelectedBiDataSource = selected ?? BiDataSources.FirstOrDefault();
        OnPropertyChanged(nameof(SelectedBiDataSource));

        var (model, _, label) = await _service.GetAiProfileInfoAsync(CancellationToken.None);
        _aiModelName = model;
        _aiModelLabel.Text = label;
    }

    private void OnNlSwitchToggled(object? sender, ToggledEventArgs e)
    {
        UseNaturalLanguage = e.Value;
        _nlModeLabel.Text = e.Value ? "Natural language (AI) ✓" : "Natural language (AI)";
        _sqlEditor.Placeholder = e.Value
            ? "Describe what you want in plain language, e.g. 'What is total revenue by month?'"
            : "SELECT * FROM your_table LIMIT 20";
        _sqlEditor.Text = string.Empty;
    }

    private async void OnRunQueryClicked(object? sender, EventArgs e)
    {
        string sql;
        if (UseNaturalLanguage)
        {
            var nlQuery = _sqlEditor.Text?.Trim() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(nlQuery))
            {
                QueryStatus = "Natural language query is required.";
                OnPropertyChanged(nameof(QueryStatus));
                return;
            }

            if (SelectedBiDataSource is null)
            {
                QueryStatus = "No BI datasource selected.";
                OnPropertyChanged(nameof(QueryStatus));
                return;
            }

            try
            {
                IsLoading = true;
                var label = string.IsNullOrWhiteSpace(_aiModelName)
                    ? "AI is analyzing..."
                    : $"⏳ {_aiModelName} is analyzing...";
                QueryStatus = label;
                OnPropertyChanged(nameof(IsLoading));
                OnPropertyChanged(nameof(QueryStatus));

                var (ok, answer, model) = await _service.AskAiAsync(nlQuery, SelectedBiDataSource.Token, MobileLocalizer.CurrentLanguage, CancellationToken.None);
                if (!string.IsNullOrWhiteSpace(model))
                {
                    _aiModelName = model;
                    _aiModelLabel.Text = model.ToUpperInvariant();
                }

                QueryStatus = ok ? "AI analysis complete." : $"AI error: {answer}";
                ResultRows.Clear();
                if (ok && !string.IsNullOrWhiteSpace(answer))
                {
                    foreach (var line in answer.Split('\n', StringSplitOptions.RemoveEmptyEntries))
                    {
                        ResultRows.Add(line);
                    }
                }

                ColumnsPreview = "AI Analysis";
                OnPropertyChanged(nameof(ColumnsPreview));
                OnPropertyChanged(nameof(QueryStatus));
            }
            finally
            {
                IsLoading = false;
                OnPropertyChanged(nameof(IsLoading));
            }

            return;
        }
        else
        {
            sql = _sqlEditor.Text?.Trim() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(sql))
            {
                QueryStatus = "SQL is required.";
                OnPropertyChanged(nameof(QueryStatus));
                return;
            }
        }

        if (SelectedBiDataSource is null)
        {
            QueryStatus = "No BI datasource selected.";
            OnPropertyChanged(nameof(QueryStatus));
            return;
        }

        if (string.IsNullOrWhiteSpace(sql))
        {
            QueryStatus = "Query is required.";
            OnPropertyChanged(nameof(QueryStatus));
            return;
        }

        try
        {
            IsLoading = true;
            QueryStatus = "Running query...";
            OnPropertyChanged(nameof(IsLoading));
            OnPropertyChanged(nameof(QueryStatus));

            var (ok, message, result) = await _service.ExecuteBiQueryAsync(sql, SelectedBiDataSource.Token, 80, CancellationToken.None);
            QueryStatus = ok ? message : $"Query failed: {message}";
            ResultRows.Clear();

            if (result is null)
            {
                ColumnsPreview = "-";
                OnPropertyChanged(nameof(ColumnsPreview));
                OnPropertyChanged(nameof(QueryStatus));
                return;
            }

            ColumnsPreview = result.Columns.Count == 0 ? "-" : string.Join(" | ", result.Columns);
            foreach (var row in result.Rows.Take(80))
            {
                ResultRows.Add(string.Join(" | ", row));
            }

            OnPropertyChanged(nameof(ColumnsPreview));
            OnPropertyChanged(nameof(QueryStatus));
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }
}
