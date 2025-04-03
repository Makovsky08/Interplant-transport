# dash_integration.py

import os
import dash
from dash import html, dcc, Input, Output, State, clientside_callback
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from flask import url_for

# Global variable to store the Dash app
dash_app = None
processed_results_cache = {}

def init_dash(flask_app):
    """
    Initialize the Dash application with the given Flask app.
    
    Args:
        flask_app: The Flask application
    """
    global dash_app


    url_base = os.getenv('DASH_URL_BASE_PATHNAME', '/')
        
    # Create a Dash app using the existing Flask server
    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname=url_base,
        assets_folder='static/dash_assets',
        suppress_callback_exceptions=True
    )
    
    # Get the active schedule for the index string
    from models.schedule import Schedule
    active_schedule = Schedule.get_active_schedule()
    active_schedule_info = ""
    
    if active_schedule:
        active_schedule_info = f"""
        <div class="navbar-text me-3">
            <span class="badge bg-success">
                <i class="bi bi-check-circle"></i>
                Aktivní jízdní řád: <strong>{active_schedule['name']}</strong>
            </span>
        </div>
        <a href="/config_module/schedules" class="btn btn-sm btn-outline-light">
            <i class="bi bi-pencil"></i> Změnit
        </a>
        """
    else:
        active_schedule_info = f"""
        <div class="navbar-text me-3">
            <span class="badge bg-warning text-dark">
                <i class="bi bi-exclamation-triangle"></i>
                Žádný aktivní jízdní řád
            </span>
        </div>
        <a href="/config_module/schedules" class="btn btn-sm btn-outline-light">
            <i class="bi bi-plus-circle"></i> Aktivovat
        </a>
        """
    
    # Custom index string to make it integrate with the Flask app's templates
    dash_app.index_string = f'''
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RCMPSP Interactive Gantt Chart</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.0/font/bootstrap-icons.css">
        <style>
            .container-fluid {{ 
                width: 95%; 
                margin: 0 auto;
                padding-top: 20px;
            }}
            .navbar {{
                margin-bottom: 5px;
                padding: 0.5rem 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .navbar-brand {{
                font-weight: 700;
                padding: 0.5rem 1rem;
                border-radius: 4px;
                margin-right: 1.5rem;
            }}
            .nav-item {{
                margin-right: 0.25rem;
            }}
            .nav-link {{
                padding: 0.6rem 1rem;
                border-radius: 4px;
                transition: all 0.2s ease;
            }}
            .nav-link:hover {{
                background-color: rgba(255,255,255,0.1);
            }}
            .nav-link.active {{
                background-color: rgba(255,255,255,0.2);
                font-weight: 500;
            }}
            .badge {{
                font-weight: 500;
                padding: 0.4rem 0.7rem;
            }}
            .view-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }}
            .view-header h1 {{
                margin-bottom: 0;
            }}
            .view-actions {{
                display: flex;
                gap: 10px;
            }}
            .view-selector {{
                margin-bottom: 20px;
                background-color: #f8f9fa;
                border-radius: 5px;
                padding: 15px;
            }}
            .view-option {{
                display: inline-block;
                padding: 10px 15px;
                margin-right: 10px;
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.2s;
                text-decoration: none;
                color: #212529;
            }}
            .view-option:hover {{
                border-color: #adb5bd;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .view-option.active {{
                border-color: #0d6efd;
                background-color: #f0f7ff;
                font-weight: 500;
            }}
        </style>
        {{%css%}}
        {{%metas%}}
        {{%favicon%}}
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container-fluid">
                <a class="navbar-brand" href="/">Mezizávodová Doprava</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarMain" aria-controls="navbarMain" aria-expanded="false" aria-label="Toggle navigation">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarMain">
                                    <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                    <li class="nav-item">
                        <a class="nav-link" aria-current="page" href="/index">
                            <i class="bi bi-house-door"></i> Domů
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/data_module/">
                            <i class="bi bi-database"></i> Analýza dat
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/config_module/">
                            <i class="bi bi-gear"></i> Konfigurace
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/config_module/planner">
                            <i class="bi bi-gear"></i> Přiřazení celků k shuttlu
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/rcmpsp/">
                            <i class="bi bi-calendar3"></i> Tvorba jízdních řádů
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="/rcmpsp/results_dash/">
                            <i class="bi bi-bar-chart"></i> Výsledky
                        </a>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="navbarDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                            <i class="bi bi-shield-lock"></i> Administrace
                        </a>
                        <ul class="dropdown-menu" aria-labelledby="navbarDropdown">
                            <li><a class="dropdown-item" href="/admin/settings">
                                <i class="bi bi-sliders"></i> Nastavení
                            </a></li>
                            <li><hr class="dropdown-divider"></li>
                        </ul>
                    </li>
                </ul>
                    
                    <!-- Active schedule info -->
                    {active_schedule_info}
                </div>
            </div>
        </nav>

        <div class="container-fluid">
            <div class="view-header">
                <h1>Interaktivní Ganttův diagram</h1>
                <div class="view-actions">
                    <a href="/rcmpsp/" class="btn btn-secondary">
                        <i class="bi bi-arrow-left"></i> Zpět do tvorby jízdních řádů
                    </a>
                </div>
            </div>
            
            {{%app_entry%}}
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
        {{%config%}}
        {{%scripts%}}
        {{%renderer%}}
    </body>
    </html>
    '''
    
    # Create the layout
    dash_app.layout = html.Div([
        # Store for data
        dcc.Store(id='gantt-data-store'),
        dcc.Store(id='trigger-export-store'),
        
        # Control panel and chart in a row
        html.Div([
            # Control panel
            html.Div([
                html.Div([
                    html.H4("Gantt diagram nastavení", className="mb-3"),
                    
                    html.Div([
                        html.Label("Scénář:", className="form-label"),
                        dcc.Dropdown(
                            id='scenario-selector',
                            options=[
                                {'label': 'Median (Average)', 'value': 'median'},
                                {'label': 'Median (Peak)', 'value': 'peak_median'},
                                {'label': 'P90 (Average)', 'value': 'p90'},
                                {'label': 'P90 (Peak)', 'value': 'peak_p90'}
                            ],
                            value='median',  # Default value
                            clearable=False,
                            className="mb-3"
                        ),
                    ], className="mb-3"),


                    html.H4("Filters", className="mb-3"),
                    
                    html.Div([
                        html.Label("Shuttly:", className="form-label"),
                        dcc.Dropdown(
                            id='shuttle-filter',
                            options=[],  # Will be filled dynamically
                            multi=True,
                            placeholder="Vyberte shuttle",
                            className="mb-3"
                        ),
                    ], className="mb-3"),
                    
                    html.Div([
                        html.Label("Závody:", className="form-label"),
                        dcc.Dropdown(
                            id='plant-filter',
                            options=[],  # Will be filled dynamically
                            multi=True,
                            placeholder="Vyberte závod",
                            className="mb-3"
                        ),
                    ], className="mb-3"),
                    
                    html.Div([
                        html.Label("Operation Types:", className="form-label"),
                        dcc.Dropdown(
                            id='operation-filter',
                            options=[
                                {'label': 'Load', 'value': 'load'},
                                {'label': 'Unload', 'value': 'unload'},
                                {'label': 'Travel', 'value': 'travel'},
                                {'label': 'Break', 'value': 'break'},
                                {'label': 'Shift Change', 'value': 'shift_change'},
                                {'label': 'Preprah', 'value': 'preprah'}
                            ],
                            multi=True,
                            placeholder="Select operations",
                            className="mb-3"
                        ),
                    ], className="mb-3"),
                    
                    html.Div([
                        html.Label("Violations:", className="form-label"),
                        dcc.RadioItems(
                            id='violation-filter',
                            options=[
                                {'label': 'Show All', 'value': 'all'},
                                {'label': 'Only Ramp Violations', 'value': 'ramp'},
                                {'label': 'Only Worker Violations', 'value': 'worker'},
                                {'label': 'All Violations', 'value': 'any'},
                                {'label': 'Hide Violations', 'value': 'hide'}
                            ],
                            value='all',
                            className="mb-3"
                        ),
                    ], className="mb-3"),
                    
                    html.Div([
                        html.Label("Time Range:", className="form-label"),
                        dcc.RangeSlider(
                            id='time-slider',
                            min=6,
                            max=18,
                            step=0.5,
                            marks={i: f'{i:02d}:00' if i % 1 == 0 else f'{int(i):02d}:30' for i in range(6, 19)},
                            value=[6, 18],
                            className="mb-2"
                        ),
                        html.Div(id='time-range-display', className="text-center small text-muted mb-3"),
                    ], className="mb-3"),
                    
                    html.Div([
                        html.Button('Apply Filters', id='apply-filters', className="btn btn-primary me-2"),
                        html.Button('Reset Filters', id='reset-filters', className="btn btn-outline-secondary")
                    ], className="d-flex justify-content-between")
                    
                ], className="p-3 bg-light rounded"),
                
                # Summary section
                html.Div([
                    html.H4("Schedule Summary", className="mb-3 mt-4"),
                    
                    html.Div([
                        html.Div([
                            html.Strong("Solution Quality:"),
                            html.Span(id="solution-quality", className="ms-2")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Strong("Total Frequencies:"),
                            html.Span(id="total-frequencies", className="ms-2")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Strong("Total Violations:"),
                            html.Span(id="total-violations", className="ms-2")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Strong("Total Idle Time:"),
                            html.Span(id="total-idle-time", className="ms-2")
                        ], className="mb-2"),
                    ], className="p-3 bg-light rounded")
                ]),

                html.Div([
                    html.H4("Export Options", className="mb-3 mt-4"),
                    
                    html.Div([
                        html.A(
                            id='export-excel-btn', 
                            className="btn btn-success w-100",
                            children=[html.I(className="bi bi-file-excel me-1"), "Export to Excel"],
                            href="javascript:void(0)",  # Výchozí hodnota
                            download=None  # Výchozí hodnota
                        ),
                        html.Div(id='export-status', className="mt-2")
                    ], className="p-3 bg-light rounded")
                ]),
                # Legend section
                html.Div([
                        html.H4("Legend", className="mb-3 mt-4"),
                    
                    html.Div([
                        html.Div([
                            html.Div(className="d-inline-block rounded me-2", 
                                    style={"width": "15px", "height": "15px", "backgroundColor": "#198754"}),
                            html.Span("Load")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Div(className="d-inline-block rounded me-2", 
                                    style={"width": "15px", "height": "15px", "backgroundColor": "#dc3545"}),
                            html.Span("Unload")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Div(className="d-inline-block rounded me-2", 
                                    style={"width": "15px", "height": "15px", "backgroundColor": "#0d6efd"}),
                            html.Span("Travel")
                        ], className="mb-2"),

                        html.Div([
                            html.Div(className="d-inline-block rounded me-2", 
                                    style={"width": "15px", "height": "15px", "backgroundColor": "#6c757d"}),
                            html.Span("Break")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Div(className="d-inline-block rounded me-2", 
                                    style={"width": "15px", "height": "15px", "backgroundColor": "#6f42c1"}),
                            html.Span("Shift Change")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Div(className="d-inline-block rounded me-2", 
                                    style={"width": "15px", "height": "15px", "backgroundColor": "#fd7e14"}),
                            html.Span("Preprah")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Div(className="d-inline-block rounded me-2", 
                                    style={"width": "15px", "height": "15px", "border": "2px solid #dc3545"}),
                            html.Span("Ramp Violation")
                        ], className="mb-2"),
                        
                        html.Div([
                            html.Div(className="d-inline-block rounded me-2", 
                                    style={"width": "15px", "height": "15px", "border": "2px dashed #ffcc00"}),
                            html.Span("Worker Violation")
                        ], className="mb-2")
                        
                    ], className="p-3 bg-light rounded")
                ]),
                
            ], className="col-md-3"),
            
            # Gantt chart
            html.Div([
                
                # Main chart
                dcc.Loading(
                    id="loading-gantt",
                    type="circle",
                    children=[
                        dcc.Graph(
                            id='gantt-chart',
                            config={
                                'displayModeBar': True,
                                'scrollZoom': True,
                                'modeBarButtonsToAdd': ['resetScale2d']
                            },
                            style={'height': '750px'}
                        )
                    ]
                )
            ], className="col-md-9"),
        ], className="row")
    ])
    
    # Initialize callbacks
    init_callbacks(dash_app)
    
    return dash_app.server

def init_callbacks(dash_app):
    """
    Initialize callbacks for the Dash application.
    
    Args:
        dash_app: The Dash application
    """
    @dash_app.callback(
    Output('solution-quality', 'className'),
    Input('solution-quality', 'children')
    )
    def update_solution_quality_class(quality):
        """Update the CSS class of the solution quality indicator based on its value."""
        if quality == "Good":
            return "ms-2 solution-good"
        elif quality == "Fair":
            return "ms-2 solution-fair"
        elif quality == "Poor":
            return "ms-2 solution-poor"
        else:
            return "ms-2"


    @dash_app.callback(
        Output('gantt-chart', 'figure'),
        [
            Input('gantt-data-store', 'data'),
            Input('apply-filters', 'n_clicks')
        ],
        [
            State('shuttle-filter', 'value'),
            State('plant-filter', 'value'),
            State('operation-filter', 'value'),
            State('violation-filter', 'value'),
            State('time-slider', 'value')
        ],
        # Add bigger cache size to store more results
        prevent_initial_call=False
    )
    def update_gantt_chart(data, n_clicks, selected_shuttles, 
                        selected_plants, selected_operations, violation_filter, time_range):
        """Update the Gantt chart based on selected filters - optimized version."""
        import time
        start_time = time.time()
        
        # Cache for storing filtered dataframes
        if not hasattr(update_gantt_chart, 'df_cache'):
            update_gantt_chart.df_cache = {}
        
        if not data:
            return empty_figure("No data available")
        
        # Generate a cache key based on filter settings
        cache_key = f"{str(selected_shuttles)}_{str(selected_plants)}_{str(selected_operations)}_{violation_filter}_{str(time_range)}"
        
        # Check if we have this result cached
        if cache_key in update_gantt_chart.df_cache:
            df = update_gantt_chart.df_cache[cache_key]
            print(f"Using cached dataframe for {cache_key}")
        else:
            # Convert string data back to python objects
            operations = data.get('operations', [])
            
            if not operations:
                return empty_figure("No operations found in data")
            
            # Convert to DataFrame for easier filtering
            df = pd.DataFrame(operations)
            
            # Apply filters
            if selected_shuttles and len(selected_shuttles) > 0:
                df = df[df['shuttle_id'].isin(selected_shuttles)]
                
            if selected_plants and len(selected_plants) > 0:
                df = df[df['plant_id'].isin(selected_plants)]
                
            if selected_operations and len(selected_operations) > 0:
                df = df[df['operation_type'].isin(selected_operations)]
                
            if violation_filter == 'ramp':
                df = df[df['violation_type'] == 'ramp']
            elif violation_filter == 'worker':
                df = df[df['violation_type'] == 'worker']
            elif violation_filter == 'any':
                df = df[df['has_violation']]
            elif violation_filter == 'hide':
                df = df[~df['has_violation']]
            
            if time_range and len(time_range) == 2:
                # Convert slider values to time strings
                start_hour, end_hour = time_range
                start_time_str = f"{int(start_hour):02d}:{int((start_hour % 1) * 60):02d}"
                end_time_str = f"{int(end_hour):02d}:{int((end_hour % 1) * 60):02d}"
                
                # Filter by time range - use vectorized operations for speed
                df = df[~((df['end_time'] <= start_time_str) | (df['start_time'] >= end_time_str))]
                
                # Add decimal times for efficient filtering
                df['start_decimal'] = df['start_time'].apply(lambda x: int(x.split(':')[0]) + int(x.split(':')[1]) / 60)
                df['end_decimal'] = df['end_time'].apply(lambda x: int(x.split(':')[0]) + int(x.split(':')[1]) / 60)
            
            # Store in cache - limit cache size to 10 entries
            if len(update_gantt_chart.df_cache) >= 10:
                # Remove oldest entry
                oldest_key = next(iter(update_gantt_chart.df_cache))
                del update_gantt_chart.df_cache[oldest_key]
                
            update_gantt_chart.df_cache[cache_key] = df
        
        if df.empty:
            return empty_figure("No operations match the current filters")
        
        # Create Gantt chart with our optimized function
        fig = create_gantt_figure(df)
        
        # Log performance
        end_time = time.time()
        print(f"Gantt chart generation took {end_time - start_time:.2f} seconds for {len(df)} operations")
        
        return fig
        

    @dash_app.callback(
        [
            Output('gantt-data-store', 'data'),
            Output('solution-quality', 'children'),
            Output('total-frequencies', 'children'),
            Output('total-violations', 'children'),
            Output('total-idle-time', 'children'),
            Output('shuttle-filter', 'options'),
            Output('plant-filter', 'options')
        ],
        [
            Input('gantt-data-store', 'id'),
            Input('scenario-selector', 'value')
        ]
    )
    def initialize_data(id, selected_scenario):
        """Initialize the data store when the page loads or scenario changes."""
        try:
            # Import the necessary models
            from models.schedule import Schedule
            from models.rcmpsp.rcmpsp_result import RcmpspResult
            from models.config_module.plant import Plant
            from models.config_module.shuttle import Shuttle
            
            # Default scenario if none selected
            scenario = selected_scenario or 'median'
            
            # Get the active schedule
            active_schedule = Schedule.get_active_schedule()
            if not active_schedule:
                empty_data = {
                    'operations': [], 
                    'summary_info': {'error': 'No active schedule found'}
                }
                return empty_data, "N/A", "N/A", "N/A", "N/A", [], []
            
            schedule_id = active_schedule['id']
            
            # Check if we have this scenario in cache
            global processed_results_cache
            cache_key = f"{schedule_id}_{scenario}"
            if cache_key in processed_results_cache:
                cached_data = processed_results_cache[cache_key]
                return (cached_data['dash_data'], 
                        cached_data['solution_quality'], 
                        cached_data['total_frequencies'], 
                        cached_data['total_violations'], 
                        cached_data['total_idle_time'], 
                        cached_data['shuttle_options'], 
                        cached_data['plant_options'])
            
            # Get the latest result for the active schedule and selected scenario
            result = RcmpspResult.get_latest_result_for_schedule_by_scenario(schedule_id, scenario)
            
            # Fall back to any scenario if specific one not found
            if not result:
                result = RcmpspResult.get_latest_result_for_schedule(schedule_id)
            
            if not result:
                empty_data = {
                    'operations': [], 
                    'summary_info': {'error': 'No results found for active schedule'}
                }
                return empty_data, "N/A", "N/A", "N/A", "N/A", [], []
            
            # Get plants for display - fetch once and reuse
            plants = Plant.get_all()
            plants_dict = {plant['identifier']: plant for plant in plants}
            
            # Get shuttles for display - fetch once and reuse
            shuttles = Shuttle.get_all()
            shuttles_dict = {shuttle['id']: shuttle for shuttle in shuttles}
            
            # Process the data for Dash
            dash_data = process_results_for_dash(result, plants_dict, shuttles_dict)
            
            # Prepare summary info for display
            summary_info = dash_data.get('summary_info', {})
            solution_quality = summary_info.get('solution_quality', 'Unknown')
            total_frequencies = str(summary_info.get('total_frequencies', 0))
            total_violations = str(summary_info.get('total_violations', 0))
            total_idle_time = f"{summary_info.get('total_idle_time', 0):.1f} minutes"
            
            # Prepare shuttle options
            shuttle_options = [
                {'label': shuttle['name'], 'value': shuttle['id']} 
                for shuttle in dash_data.get('shuttles', [])
            ]
            
            # Prepare plant options
            plant_options = [
                {'label': plant['name'], 'value': plant['id']} 
                for plant in dash_data.get('plants', [])
            ]
            
            # Store in cache using scenario-specific key
            processed_results_cache[cache_key] = {
                'dash_data': dash_data,
                'solution_quality': solution_quality,
                'total_frequencies': total_frequencies,
                'total_violations': total_violations,
                'total_idle_time': total_idle_time,
                'shuttle_options': shuttle_options,
                'plant_options': plant_options,
                'result_id': result['id']
            }
            
            return dash_data, solution_quality, total_frequencies, total_violations, total_idle_time, shuttle_options, plant_options
        except Exception as e:
            import traceback
            print(f"Error loading data: {str(e)}")
            print(traceback.format_exc())
            empty_data = {
                'operations': [], 
                'summary_info': {'error': str(e)}
            }
            return empty_data, "Error", "Error", "Error", "Error", [], []
        
    @dash_app.callback(
        [Output('export-excel-btn', 'href'),
        Output('export-excel-btn', 'download'),
        Output('export-excel-btn', 'className'),
        Output('export-excel-btn', 'children'),
        Output('export-status', 'children')],
        Input('export-excel-btn', 'n_clicks'),
        [State('gantt-data-store', 'data'),
        State('scenario-selector', 'value')],
        prevent_initial_call=True
    )
    def transform_button_to_link(n_clicks, data, selected_scenario):
        """Transform export button to a download link."""
        if not n_clicks or not data:
            return "", "", "btn btn-success w-100", "Export to Excel", ""
        
        try:
            from models.schedule import Schedule
            from models.rcmpsp.rcmpsp_result import RcmpspResult
            
            active_schedule = Schedule.get_active_schedule()
            if not active_schedule:
                return "", "", "btn btn-success w-100", "Export to Excel", html.Div("Není nalezen žádný aktivní jízdní řád.", className="text-danger")
            
            schedule_id = active_schedule['id']
            scenario = selected_scenario or 'median'
            
            global processed_results_cache
            cache_key = f"{schedule_id}_{scenario}"
            
            if cache_key in processed_results_cache and 'result_id' in processed_results_cache[cache_key]:
                result_id = processed_results_cache[cache_key]['result_id']
            else:
                result = RcmpspResult.get_latest_result_for_schedule_by_scenario(schedule_id, scenario)
                if not result:
                    result = RcmpspResult.get_latest_result_for_schedule(schedule_id)
                if not result:
                    return "", "", "btn btn-success w-100", "Export to Excel", html.Div("Pro aktivní jízdní řád nebyly nalezeny žádné výsledky.", className="text-danger")
                result_id = result['id']
            
            download_url = f"/rcmpsp/export_result/{result_id}"
            filename = f"rcmpsp_result_{result_id}.xlsx"
            
            # Změnit tlačítko na download odkaz
            return (
                download_url,
                filename,
                "btn btn-success w-100",  # Zachování stylu tlačítka
                [html.I(className="bi bi-file-excel me-1"), "Stáhnout Excel"],  # Změna textu tlačítka
                html.Div([
                    html.Div("Export připraven. Kliknutím stáhnete soubor.", className="text-success"),
                    # Auto-klik script
                    html.Script(f'''
                        setTimeout(function() {{
                            console.log("Auto-clicking export button");
                            document.getElementById("export-excel-btn").click();
                        }}, 500);
                    ''')
                ])
            )
            
        except Exception as e:
            import traceback
            print(f"Chyba při přípravě exportu: {str(e)}")
            print(traceback.format_exc())
            return "", "", "btn btn-success w-100", "Export to Excel", html.Div(f"Chyba: {str(e)}", className="text-danger")

    # Callback to update the time range display
    @dash_app.callback(
        Output('time-range-display', 'children'),
        Input('time-slider', 'value')
    )
    def update_time_display(time_range):
        """Update the display of the selected time range."""
        if not time_range or len(time_range) != 2:
            return "06:00 - 18:00"
        
        start_hour, end_hour = time_range
        start_time = f"{int(start_hour):02d}:{int((start_hour % 1) * 60):02d}"
        end_time = f"{int(end_hour):02d}:{int((end_hour % 1) * 60):02d}"
        
        return f"{start_time} - {end_time}"
    
    # Callback to reset filters
    @dash_app.callback(
        [
            Output('shuttle-filter', 'value'),
            Output('plant-filter', 'value'),
            Output('operation-filter', 'value'),
            Output('violation-filter', 'value'),
            Output('time-slider', 'value')
        ],
        Input('reset-filters', 'n_clicks'),
        prevent_initial_call=True
    )
    def reset_filters(n_clicks):
        """Reset all filters to their default values."""
        return [], [], [], 'all', [6, 18]

def process_results_for_dash(result, plants_dict, shuttles_dict):
    """
    Process RCMPSP result operations into data for Dash visualization.
    Simplified version focused on plant view.
    
    Args:
        result (dict): RCMPSP result with operations
        plants_dict (dict): Dictionary of plants by identifier
        shuttles_dict (dict): Dictionary of shuttles by id
        
    Returns:
        dict: JSON-serializable data for Dash
    """
    # Create a list of operations
    operations = []
    
    # Create lookup dictionaries for plants
    plants_by_identifier = {}
    plants_by_id = {}
    
    for plant_id, plant in plants_dict.items():
        # Store by identifier
        plants_by_identifier[str(plant_id)] = plant
        
        # Store by id if available
        if 'id' in plant:
            plants_by_id[str(plant['id'])] = plant
    
    # Track ramp allocations for each plant
    plant_ramp_allocations = {}
    
    # Sort operations chronologically
    sorted_operations = sorted(result['operations'], 
                               key=lambda op: datetime.fromisoformat(op['start_time']))
    
    # First pass: collect all operations except travel and preprah
    regular_operations = []
    travel_operations = []
    preprah_operations = []
    
    for op in sorted_operations:
        operation_type = op.get('operation_type')
        
        if operation_type == 'travel':
            travel_operations.append(op)
        elif operation_type == 'preprah':
            preprah_operations.append(op)
        else:
            regular_operations.append(op)
    
    # Process operations and allocate ramps
    for op in regular_operations + preprah_operations:
        shuttle_id = op['shuttle_id']
        operation_type = op['operation_type']
        
        # Parse times
        start_time_obj = datetime.fromisoformat(op['start_time'])
        end_time_obj = datetime.fromisoformat(op['end_time'])
        start_time = start_time_obj.strftime('%H:%M')
        end_time = end_time_obj.strftime('%H:%M')
        
        # Convert to decimal hours for ramp allocation
        start_decimal = start_time_obj.hour + start_time_obj.minute / 60
        end_decimal = end_time_obj.hour + end_time_obj.minute / 60
        
        # Get plant information
        plant_id = op.get('plant_id')
        if not plant_id:
            continue  # Skip if no plant ID
        
        # Find the plant
        plant = None
        plant_identifier = None
        
        if str(plant_id) in plants_by_id:
            plant = plants_by_id[str(plant_id)]
            if 'identifier' in plant:
                plant_identifier = plant['identifier']
        elif str(plant_id) in plants_by_identifier:
            plant = plants_by_identifier[str(plant_id)]
            plant_identifier = plant_id
            plant_id = plant.get('id')
        
        if not plant:
            continue  # Skip if plant not found
            
        plant_name = plant.get('name', f"Plant {plant_id}")
        
        # Get plant capacities directly from the plant data
        ramp_capacity = plant.get('ramp_capacity', 5)
        worker_capacity = plant.get('worker_capacity', 2)
        
        # Ensure capacities are integers
        try:
            ramp_capacity = int(ramp_capacity)
            if ramp_capacity <= 0:
                ramp_capacity = 5  # Default if invalid
        except (ValueError, TypeError):
            ramp_capacity = 5  # Default if conversion fails
            
        try:
            worker_capacity = int(worker_capacity)
            if worker_capacity <= 0:
                worker_capacity = 2  # Default if invalid
        except (ValueError, TypeError):
            worker_capacity = 2  # Default if conversion fails
        
        # Initialize ramp allocations for this plant if not already done
        if plant_id not in plant_ramp_allocations:
            plant_ramp_allocations[plant_id] = []
        
        # Find an available ramp
        ramp_idx = -1  # Default to Wait area
        
        # Handle different operation types
        if operation_type == 'preprah':
            # For preprah operations, try to find two adjacent ramps
            for r in range(ramp_capacity - 1):  # Need room for adjacent ramp
                r = int(r)  # Ensure r is an integer
                main_available = True
                secondary_available = True
                
                # Check if both ramps are available during this time
                for allocation in plant_ramp_allocations[plant_id]:
                    if allocation['ramp_idx'] == r:
                        if not (end_decimal <= allocation['start_decimal'] or 
                                start_decimal >= allocation['end_decimal']):
                            main_available = False
                    
                    if allocation['ramp_idx'] == r + 1:
                        if not (end_decimal <= allocation['start_decimal'] or 
                                start_decimal >= allocation['end_decimal']):
                            secondary_available = False
                
                if main_available and secondary_available:
                    ramp_idx = r
                    break
        else:
            # For regular operations, find any available ramp
            for r in range(ramp_capacity):
                r = int(r)  # Ensure r is an integer
                available = True
                
                for allocation in plant_ramp_allocations[plant_id]:
                    if allocation['ramp_idx'] == r:
                        if not (end_decimal <= allocation['start_decimal'] or 
                                start_decimal >= allocation['end_decimal']):
                            available = False
                            break
                
                if available:
                    ramp_idx = r
                    break
        
        # Allocate the ramp(s)
        if ramp_idx >= 0:
            # Add allocation for the main ramp
            plant_ramp_allocations[plant_id].append({
                'start_decimal': start_decimal,
                'end_decimal': end_decimal,
                'shuttle_id': shuttle_id,
                'ramp_idx': ramp_idx
            })
            
            # For preprah operations, also allocate the adjacent ramp
            if operation_type == 'preprah':
                plant_ramp_allocations[plant_id].append({
                    'start_decimal': start_decimal,
                    'end_decimal': end_decimal,
                    'shuttle_id': shuttle_id,
                    'ramp_idx': ramp_idx + 1
                })
        
        # Get shuttle info
        shuttle = shuttles_dict.get(shuttle_id, {'name': f"Shuttle {shuttle_id}"})
        shuttle_name = shuttle.get('name', f"Shuttle {shuttle_id}")
        
        # Create a consistent color for the shuttle
        shuttle_color = f"#{abs(hash(shuttle_name)) % 16777215:06x}"
        
        # Create operation record
        operation = {
            'shuttle_id': shuttle_id,
            'shuttle_name': shuttle_name,
            'shuttle_color': shuttle_color,
            'operation_type': operation_type,
            'start_time': start_time,
            'end_time': end_time,
            'duration': op['duration'],
            'plant_id': plant_id,
            'plant_identifier': plant_identifier,
            'plant_name': plant_name,
            'ramp_idx': ramp_idx,  # -1 means Wait area
            'has_violation': bool(op.get('has_violation', False)),
            'violation_type': op.get('violation_type', ''),
            'is_preprah_operation': operation_type == 'preprah',
            'frequency_num': op.get('frequency_num', 0),
            'ramp_capacity': ramp_capacity,
            'worker_capacity': worker_capacity
        }
        
        operations.append(operation)
        
        # For preprah operations, add a second operation for the adjacent ramp
        if operation_type == 'preprah' and ramp_idx >= 0:
            secondary_operation = {
                'shuttle_id': shuttle_id,
                'shuttle_name': shuttle_name,
                'shuttle_color': shuttle_color,
                'operation_type': operation_type,
                'start_time': start_time,
                'end_time': end_time,
                'duration': op['duration'],
                'plant_id': plant_id,
                'plant_identifier': plant_identifier,
                'plant_name': plant_name,
                'ramp_idx': ramp_idx + 1,  # Adjacent ramp
                'has_violation': bool(op.get('has_violation', False)),
                'violation_type': op.get('violation_type', ''),
                'is_preprah_operation': True,
                'is_secondary_preprah': True,
                'frequency_num': op.get('frequency_num', 0),
                'ramp_capacity': ramp_capacity,
                'worker_capacity': worker_capacity
            }
            operations.append(secondary_operation)
    
    # Process travel operations
    for op in travel_operations:
        shuttle_id = op['shuttle_id']
        
        # Parse times
        start_time = datetime.fromisoformat(op['start_time']).strftime('%H:%M')
        end_time = datetime.fromisoformat(op['end_time']).strftime('%H:%M')
        
        # Get shuttle info
        shuttle = shuttles_dict.get(shuttle_id, {'name': f"Shuttle {shuttle_id}"})
        shuttle_name = shuttle.get('name', f"Shuttle {shuttle_id}")
        shuttle_color = f"#{abs(hash(shuttle_name)) % 16777215:06x}"
        
        # Process from and to plants
        from_plant_id = op.get('from_plant_id')
        to_plant_id = op.get('to_plant_id')
        
        from_plant_name = "Unknown"
        to_plant_name = "Unknown"
        
        # Get from_plant details
        if from_plant_id:
            if str(from_plant_id) in plants_by_id:
                from_plant = plants_by_id[str(from_plant_id)]
                from_plant_name = from_plant.get('name', f"Plant {from_plant_id}")
            elif str(from_plant_id) in plants_by_identifier:
                from_plant = plants_by_identifier[str(from_plant_id)]
                from_plant_name = from_plant.get('name', f"Plant {from_plant_id}")
        
        # Get to_plant details
        if to_plant_id:
            if str(to_plant_id) in plants_by_id:
                to_plant = plants_by_id[str(to_plant_id)]
                to_plant_name = to_plant.get('name', f"Plant {to_plant_id}")
            elif str(to_plant_id) in plants_by_identifier:
                to_plant = plants_by_identifier[str(to_plant_id)]
                to_plant_name = to_plant.get('name', f"Plant {to_plant_id}")
        
        # Create travel operation
        operation = {
            'shuttle_id': shuttle_id,
            'shuttle_name': shuttle_name,
            'shuttle_color': shuttle_color,
            'operation_type': 'travel',
            'start_time': start_time,
            'end_time': end_time,
            'duration': op['duration'],
            'plant_id': from_plant_id,
            'plant_name': from_plant_name,
            'from_plant_id': from_plant_id,
            'from_plant_name': from_plant_name,
            'to_plant_id': to_plant_id,
            'to_plant_name': to_plant_name,
            'ramp_idx': -1,  # Travel operations don't use a ramp
            'has_violation': bool(op.get('has_violation', False)),
            'violation_type': op.get('violation_type', ''),
            'is_preprah_operation': False
        }
        
        operations.append(operation)
    
    # Prepare summary information
    summary_info = {
        'total_violations': result.get('total_violations', 0),
        'total_frequencies': result.get('total_frequencies', 0),
        'total_idle_time': result.get('total_idle_time', 0),
        'solution_quality': result.get('solution_quality', 'Unknown')
    }
    
    # Get time range
    min_time = min([op['start_time'] for op in operations]) if operations else "06:00"
    max_time = max([op['end_time'] for op in operations]) if operations else "18:00"
    
    # Get unique shuttles and plants
    shuttles = []
    plants = []
    
    for op in operations:
        if op['shuttle_id'] not in [s['id'] for s in shuttles]:
            shuttles.append({
                'id': op['shuttle_id'],
                'name': op['shuttle_name'],
                'color': op['shuttle_color']
            })
        
        if op['plant_id'] and op['plant_id'] not in [p['id'] for p in plants]:
            plants.append({
                'id': op['plant_id'],
                'identifier': op.get('plant_identifier'),
                'name': op['plant_name'],
                'ramp_capacity': op.get('ramp_capacity', 5),
                'worker_capacity': op.get('worker_capacity', 2)
            })
    
    return {
        'operations': operations,
        'summary_info': summary_info,
        'time_range': {
            'min_time': min_time,
            'max_time': max_time
        },
        'shuttles': shuttles,
        'plants': plants
    }

def find_available_ramp(ramp_allocations, start_decimal, end_decimal, ramp_capacity):
    """
    Find an available ramp in the plant for the given time period.
    
    Args:
        ramp_allocations (list): List of existing ramp allocations
        start_decimal (float): Operation start time in decimal hours
        end_decimal (float): Operation end time in decimal hours
        ramp_capacity (int): Number of ramps available at the plant
        
    Returns:
        int: Ramp index if available (0 to ramp_capacity-1), or -1 for Wait area
    """
    # Check each ramp for availability
    for ramp_idx in range(ramp_capacity):
        is_available = True
        
        # Check if this ramp is already allocated during our time period
        for allocation in ramp_allocations:
            if allocation['ramp_idx'] == ramp_idx:
                # Check if time periods overlap
                if not (end_decimal <= allocation['start_decimal'] or start_decimal >= allocation['end_decimal']):
                    is_available = False
                    break
        
        if is_available:
            return ramp_idx
    
    # If no ramps are available, return -1 (Wait area)
    return -1

def process_travel_operation(op, operations, plants_by_id, plants_by_identifier, shuttles_dict):
    """
    Process a travel operation and add it to the operations list.
    
    Args:
        op (dict): Travel operation data
        operations (list): List to append the processed operation to
        plants_by_id (dict): Plants lookup by ID
        plants_by_identifier (dict): Plants lookup by identifier
        shuttles_dict (dict): Shuttles lookup
    """
    shuttle_id = op['shuttle_id']
    
    # Parse times
    start_time = datetime.fromisoformat(op['start_time']).strftime('%H:%M')
    end_time = datetime.fromisoformat(op['end_time']).strftime('%H:%M')
    
    # Get shuttle info
    shuttle = shuttles_dict.get(shuttle_id, {'name': f"Shuttle {shuttle_id}"})
    shuttle_name = shuttle.get('name', f"Shuttle {shuttle_id}")
    
    # Create a consistent color for the shuttle
    shuttle_color = f"#{abs(hash(shuttle_name)) % 16777215:06x}"
    
    # Process from plant
    from_plant_id = op.get('from_plant_id')
    from_plant_name = "Unknown"
    from_plant_identifier = None
    
    if from_plant_id:
        # Try to find plant using id or identifier
        if str(from_plant_id) in plants_by_id:
            from_plant = plants_by_id[str(from_plant_id)]
            from_plant_name = from_plant.get('name', f"Plant {from_plant_id}")
            from_plant_identifier = from_plant.get('identifier')
        elif str(from_plant_id) in plants_by_identifier:
            from_plant = plants_by_identifier[str(from_plant_id)]
            from_plant_name = from_plant.get('name', f"Plant {from_plant_id}")
            from_plant_identifier = from_plant_id
            from_plant_id = from_plant.get('id')
        else:
            from_plant_name = f"Plant {from_plant_id}"
    
    # Process to plant
    to_plant_id = op.get('to_plant_id')
    to_plant_name = "Unknown"
    to_plant_identifier = None
    
    if to_plant_id:
        # Try to find plant using id or identifier
        if str(to_plant_id) in plants_by_id:
            to_plant = plants_by_id[str(to_plant_id)]
            to_plant_name = to_plant.get('name', f"Plant {to_plant_id}")
            to_plant_identifier = to_plant.get('identifier')
        elif str(to_plant_id) in plants_by_identifier:
            to_plant = plants_by_identifier[str(to_plant_id)]
            to_plant_name = to_plant.get('name', f"Plant {to_plant_id}")
            to_plant_identifier = to_plant_id
            to_plant_id = to_plant.get('id')
        else:
            to_plant_name = f"Plant {to_plant_id}"
    
    # Create operation record
    operation = {
        'shuttle_id': shuttle_id,
        'shuttle_name': shuttle_name,
        'shuttle_color': shuttle_color,
        'operation_type': 'travel',
        'start_time': start_time,
        'end_time': end_time,
        'duration': op['duration'],
        'plant_id': from_plant_id,  # Use from_plant for general plant association
        'plant_identifier': from_plant_identifier,
        'plant_name': from_plant_name,
        'from_plant_id': from_plant_id,
        'from_plant_name': from_plant_name,
        'from_plant_identifier': from_plant_identifier,
        'to_plant_id': to_plant_id,
        'to_plant_name': to_plant_name,
        'to_plant_identifier': to_plant_identifier,
        'ramp_idx': -1,  # Travel doesn't use a ramp
        'has_violation': bool(op.get('has_violation', False)),
        'violation_type': op.get('violation_type'),
        'is_preprah_operation': False,
        'frequency_num': op.get('frequency_num', 0)
    }
    
    operations.append(operation)

def process_preprah_operation(op, operations, plant_ramp_allocations, plants_by_id, plants_by_identifier, shuttles_dict, plant_capacities):
    """
    Process a preprah operation and add it to the operations list.
    Preprah operations need two adjacent ramps.
    
    Args:
        op (dict): Preprah operation data
        operations (list): List to append the processed operation to
        plant_ramp_allocations (dict): Current ramp allocations by plant
        plants_by_id (dict): Plants lookup by ID
        plants_by_identifier (dict): Plants lookup by identifier
        shuttles_dict (dict): Shuttles lookup
        plant_capacities (dict): Dictionary of plant capacity information
    """
    shuttle_id = op['shuttle_id']
    plant_id = op.get('plant_id')
    
    if not plant_id:
        return  # Skip operations without a plant
    
    # Parse times
    start_time_obj = datetime.fromisoformat(op['start_time'])
    end_time_obj = datetime.fromisoformat(op['end_time'])
    start_time = start_time_obj.strftime('%H:%M')
    end_time = end_time_obj.strftime('%H:%M')
    
    # Convert to decimal hours for easier comparison
    start_decimal = start_time_obj.hour + start_time_obj.minute / 60
    end_decimal = end_time_obj.hour + end_time_obj.minute / 60
    
    # Try to find plant information
    plant = None
    plant_identifier = None
    
    if str(plant_id) in plants_by_id:
        plant = plants_by_id[str(plant_id)]
        if 'identifier' in plant:
            plant_identifier = plant['identifier']
    elif str(plant_id) in plants_by_identifier:
        plant = plants_by_identifier[str(plant_id)]
        plant_identifier = plant_id
        plant_id = plant.get('id')
    
    if not plant:
        return  # Skip if we can't find the plant
        
    plant_name = plant.get('name', f"Plant {plant_id}")
    
    # Get the ramp capacity and worker capacity for this plant using our lookup
    plant_capacity_info = plant_capacities.get(str(plant_id), {'ramp_capacity': 5, 'worker_capacity': 2})
    ramp_capacity = plant_capacity_info['ramp_capacity']
    worker_capacity = plant_capacity_info['worker_capacity']
    
    # Initialize ramp allocations for this plant if not already done
    if plant_id not in plant_ramp_allocations:
        plant_ramp_allocations[plant_id] = []
    
    # For preprah, we need to find two adjacent available ramps
    main_ramp_idx = -1
    secondary_ramp_idx = -1
    
    # Check each ramp for availability (and its adjacent ramp)
    for ramp_idx in range(ramp_capacity - 1):  # -1 because we need an adjacent ramp
        main_is_available = True
        secondary_is_available = True
        adjacent_idx = ramp_idx + 1
        
        # Check if these ramps are already allocated during our time period
        for allocation in plant_ramp_allocations[plant_id]:
            # Check main ramp
            if allocation['ramp_idx'] == ramp_idx:
                if not (end_decimal <= allocation['start_decimal'] or start_decimal >= allocation['end_decimal']):
                    main_is_available = False
            
            # Check adjacent ramp
            if allocation['ramp_idx'] == adjacent_idx:
                if not (end_decimal <= allocation['start_decimal'] or start_decimal >= allocation['end_decimal']):
                    secondary_is_available = False
        
        # If both ramps are available, use them
        if main_is_available and secondary_is_available:
            main_ramp_idx = ramp_idx
            secondary_ramp_idx = adjacent_idx
            break
    
    # If we found two adjacent ramps, allocate them
    if main_ramp_idx >= 0 and secondary_ramp_idx >= 0:
        # Add allocations for both ramps
        plant_ramp_allocations[plant_id].append({
            'start_decimal': start_decimal,
            'end_decimal': end_decimal,
            'shuttle_id': shuttle_id,
            'ramp_idx': main_ramp_idx
        })
        
        plant_ramp_allocations[plant_id].append({
            'start_decimal': start_decimal,
            'end_decimal': end_decimal,
            'shuttle_id': shuttle_id,
            'ramp_idx': secondary_ramp_idx
        })
    else:
        # Try allocating just one ramp if we can't get adjacent ramps
        # This is a fallback to ensure preprah operations still appear somewhere
        single_ramp_idx = find_available_ramp(
            plant_ramp_allocations[plant_id], 
            start_decimal, 
            end_decimal, 
            ramp_capacity
        )
        
        if single_ramp_idx >= 0:
            # If we found at least one ramp, use it
            main_ramp_idx = single_ramp_idx
            
            plant_ramp_allocations[plant_id].append({
                'start_decimal': start_decimal,
                'end_decimal': end_decimal,
                'shuttle_id': shuttle_id,
                'ramp_idx': main_ramp_idx
            })
            
            # Try to find a non-adjacent ramp if possible
            remaining_ramps = [i for i in range(ramp_capacity) if i != main_ramp_idx]
            for ramp_idx in remaining_ramps:
                is_available = True
                
                # Check if this ramp is already allocated during our time period
                for allocation in plant_ramp_allocations[plant_id]:
                    if allocation['ramp_idx'] == ramp_idx:
                        if not (end_decimal <= allocation['start_decimal'] or start_decimal >= allocation['end_decimal']):
                            is_available = False
                            break
                
                if is_available:
                    secondary_ramp_idx = ramp_idx
                    
                    plant_ramp_allocations[plant_id].append({
                        'start_decimal': start_decimal,
                        'end_decimal': end_decimal,
                        'shuttle_id': shuttle_id,
                        'ramp_idx': secondary_ramp_idx
                    })
                    break
    
    # Get shuttle info
    shuttle = shuttles_dict.get(shuttle_id, {'name': f"Shuttle {shuttle_id}"})
    shuttle_name = shuttle.get('name', f"Shuttle {shuttle_id}")
    
    # Create a consistent color for the shuttle
    shuttle_color = f"#{abs(hash(shuttle_name)) % 16777215:06x}"
    
    # Create operation records for both ramps (or wait area)
    
    # Main operation
    main_operation = {
        'shuttle_id': shuttle_id,
        'shuttle_name': shuttle_name,
        'shuttle_color': shuttle_color,
        'operation_type': 'preprah',
        'start_time': start_time,
        'end_time': end_time,
        'duration': op['duration'],
        'plant_id': plant_id,
        'plant_identifier': plant_identifier,
        'plant_name': plant_name,
        'ramp_idx': main_ramp_idx,
        'has_violation': bool(op.get('has_violation', False)),
        'violation_type': op.get('violation_type'),
        'is_preprah_operation': True,
        'is_secondary_preprah': False,
        'frequency_num': op.get('frequency_num', 0),
        'worker_capacity': worker_capacity,
        'ramp_capacity': ramp_capacity
    }
    operations.append(main_operation)
    
    # If we found adjacent ramps, add secondary operation
    if main_ramp_idx >= 0 and secondary_ramp_idx >= 0:
        secondary_operation = {
            'shuttle_id': shuttle_id,
            'shuttle_name': shuttle_name,
            'shuttle_color': shuttle_color,
            'operation_type': 'preprah',
            'start_time': start_time,
            'end_time': end_time,
            'duration': op['duration'],
            'plant_id': plant_id,
            'plant_identifier': plant_identifier,
            'plant_name': plant_name,
            'ramp_idx': secondary_ramp_idx,
            'has_violation': bool(op.get('has_violation', False)),
            'violation_type': op.get('violation_type'),
            'is_preprah_operation': True,
            'is_secondary_preprah': True,
            'frequency_num': op.get('frequency_num', 0),
            'worker_capacity': worker_capacity,
            'ramp_capacity': ramp_capacity
        }
        operations.append(secondary_operation)

def create_gantt_figure(df):
    """
    Create a Gantt chart figure from a DataFrame of operations with performance optimizations.
    """
    # Efficiently create plant info dict with list comprehension
    plants = sorted(df['plant_name'].unique())
    
    # Create streamlined plant information dictionary
    plant_info = {}
    for plant_name in plants:
        plant_rows = df[df['plant_name'] == plant_name]
        if not plant_rows.empty:
            first_row = plant_rows.iloc[0]
            
            # Get capacities with safer default conversion
            try:
                ramp_capacity = int(first_row.get('ramp_capacity', 5))
                if ramp_capacity <= 0:
                    ramp_capacity = 5
            except (ValueError, TypeError):
                ramp_capacity = 5
                
            try:
                worker_capacity = int(first_row.get('worker_capacity', 2))
                if worker_capacity <= 0:
                    worker_capacity = 2
            except (ValueError, TypeError):
                worker_capacity = 2
                
            plant_info[plant_name] = {
                'ramp_capacity': ramp_capacity,
                'worker_capacity': worker_capacity
            }
        else:
            plant_info[plant_name] = {'ramp_capacity': 5, 'worker_capacity': 2}
    
    # Efficiently build y-axis values
    y_values = []
    for plant_name in plants:
        ramp_capacity = plant_info[plant_name]['ramp_capacity']
        y_values.append(f"{plant_name} - Wait")
        y_values.extend([f"{plant_name} - Ramp {i+1}" for i in range(ramp_capacity)])
    
    # Create figure
    fig = go.Figure()
    
    # Create y-axis mapping once
    df['y_axis'] = df.apply(lambda row: 
        f"{row['plant_name']} - Wait" if row['ramp_idx'] == -1 
        else f"{row['plant_name']} - Ramp {row['ramp_idx'] + 1}", 
        axis=1
    )
    
    # Decimal time conversion - vectorized operations
    if 'start_decimal' not in df.columns:
        df['start_decimal'] = df['start_time'].apply(lambda x: int(x.split(':')[0]) + int(x.split(':')[1]) / 60)
        df['end_decimal'] = df['end_time'].apply(lambda x: int(x.split(':')[0]) + int(x.split(':')[1]) / 60)
    
    # Create color mapping
    color_map = {
        'load': '#198754',    # Green
        'unload': '#dc3545',  # Red
        'travel': '#0d6efd',  # Blue
        'break': '#6c757d',   # Gray
        'shift_change': '#6f42c1',  # Purple
        'preprah': '#fd7e14'  # Orange
    }
    
    # Separate travel operations
    travel_ops = df[df['operation_type'] == 'travel']
    non_travel_ops = df[df['operation_type'] != 'travel']
    
    # Process non-travel operations in bulk (much faster)
    for _, row in non_travel_ops.iterrows():
        # Get color from map
        base_color = color_map.get(row['operation_type'], row['shuttle_color'])
        
        # Adjust opacity
        opacity = 0.5 if row['operation_type'] == 'break' else 1.0
        
        # Create marker line for violations
        marker_line = dict(width=0)
        if row['has_violation']:
            marker_line = dict(
                color='#ffcc00' if row['violation_type'] == 'worker' else 'red',
                width=2
            )
        
        # Operation label map
        label_map = {
            'load': "Nakládka",
            'unload': "Vykládka",
            'preprah': "Přeprah",
            'break': "Přestávka",
            'shift_change': "Výměna směny"
        }
        operation_label = label_map.get(row['operation_type'], "")
        
        # Hover text
        hover_text = (
            f"<b>{row['shuttle_name']}</b><br>"
            f"Operation: {row['operation_type']}<br>"
            f"Time: {row['start_time']} - {row['end_time']}<br>"
            f"Duration: {row['duration']} min<br>"
            f"Plant: {row['plant_name']}"
        )
        
        if row['ramp_idx'] >= 0:
            hover_text += f"<br>Ramp: {row['ramp_idx'] + 1}"
        
        if row['has_violation']:
            hover_text += f"<br><b>Violation: {row['violation_type']}</b>"
        
        if row.get('is_preprah_operation'):
            hover_text += "<br><b>Preprah Operation</b>"
        
        # Add bar for operation - only include essential info
        fig.add_trace(go.Bar(
            x=[row['end_decimal'] - row['start_decimal']],
            y=[row['y_axis']],
            orientation='h',
            base=row['start_decimal'],
            marker=dict(
                color=base_color,
                opacity=opacity,
                line=marker_line
            ),
            hoverinfo='text',
            hovertext=hover_text,
            name=row['shuttle_name'],
            text=f"{operation_label} {row['shuttle_name'].split(' ')[-1]}",
            textposition="inside",
            textfont=dict(size=10, color="black"),
            insidetextanchor="middle"
        ))
    
    # Process travel operations more efficiently
    if not travel_ops.empty:
        # Create a lookup to find operations more efficiently
        shuttle_plant_ops = {}
        for _, row in non_travel_ops.iterrows():
            shuttle_id = row['shuttle_id']
            plant_name = row['plant_name']
            
            key = f"{shuttle_id}_{plant_name}"
            if key not in shuttle_plant_ops:
                shuttle_plant_ops[key] = []
                
            shuttle_plant_ops[key].append({
                'start_decimal': row['start_decimal'],
                'end_decimal': row['end_decimal'],
                'ramp_idx': row['ramp_idx'],
                'y_axis': row['y_axis']
            })
        
        # Sort operations by time
        for key in shuttle_plant_ops:
            shuttle_plant_ops[key].sort(key=lambda x: x['start_decimal'])
        
        # Process each travel op
        for _, row in travel_ops.iterrows():
            if not (row.get('from_plant_name') and row.get('to_plant_name')):
                continue
                
            shuttle_id = row['shuttle_id']
            start_decimal = row['start_decimal']
            end_decimal = row['end_decimal']
            
            # Find source and destination using our lookup
            from_key = f"{shuttle_id}_{row['from_plant_name']}"
            to_key = f"{shuttle_id}_{row['to_plant_name']}"
            
            from_y_axis = f"{row['from_plant_name']} - Wait"  # Default
            to_y_axis = f"{row['to_plant_name']} - Wait"  # Default
            
            # Find source operation
            if from_key in shuttle_plant_ops:
                # Find the last operation before travel
                source_ops = [op for op in shuttle_plant_ops[from_key] 
                             if op['end_decimal'] <= start_decimal]
                if source_ops:
                    # Get the last one
                    from_op = max(source_ops, key=lambda x: x['end_decimal'])
                    if from_op['ramp_idx'] >= 0:
                        from_y_axis = from_op['y_axis']
            
            # Find destination operation
            if to_key in shuttle_plant_ops:
                # Find the first operation after travel
                dest_ops = [op for op in shuttle_plant_ops[to_key] 
                           if op['start_decimal'] >= end_decimal]
                if dest_ops:
                    # Get the first one
                    to_op = min(dest_ops, key=lambda x: x['start_decimal'])
                    if to_op['ramp_idx'] >= 0:
                        to_y_axis = to_op['y_axis']
            
            # Only draw if both axes are in our y_values
            if from_y_axis in y_values and to_y_axis in y_values:
                from_y_pos = y_values.index(from_y_axis)
                to_y_pos = y_values.index(to_y_axis)
                
                # Use a curved line to represent travel between plants
                x_mid = (start_decimal + end_decimal) / 2
                
                # Calculate curve
                if from_y_pos < to_y_pos:  # Going down
                    mid_y = (from_y_pos + to_y_pos) / 2 + 0.5
                else:  # Going up
                    mid_y = (from_y_pos + to_y_pos) / 2 - 0.5
                
                # Create path
                path = f'M {start_decimal},{from_y_pos} Q {x_mid},{mid_y} {end_decimal},{to_y_pos}'
                
                # Add travel path
                fig.add_shape(
                    type="path",
                    path=path,
                    line=dict(color=row['shuttle_color'], width=2, dash="dash")
                )
                
                # Add shuttle label
                fig.add_annotation(
                    x=x_mid,
                    y=mid_y,
                    text=f"S{row['shuttle_name'].split(' ')[-1]}",
                    showarrow=False,
                    font=dict(size=8, color=row['shuttle_color']),
                    bgcolor="rgba(255, 255, 255, 0.7)",
                    bordercolor=row['shuttle_color'],
                    borderwidth=1,
                    borderpad=1,
                    opacity=0.8
                )
    
    # Prepare y-axis labels more efficiently
    tickvals = list(range(len(y_values)))
    ticktext = []
    
    for i, y_val in enumerate(y_values):
        parts = y_val.split(' - ')
        plant_name = parts[0]
        ramp_info = parts[1]
        
        # Find first occurrence of this plant efficiently
        first_idx = next((j for j, val in enumerate(y_values) if val.startswith(plant_name)), None)
        
        if i == first_idx:
            worker_count = plant_info[plant_name]['worker_capacity']
            # First row includes plant name and worker count
            if ramp_info == 'Wait':
                ticktext.append(f"{plant_name} ({worker_count} workers)\nWait")
            else:
                ticktext.append(f"{plant_name} ({worker_count} workers)\n{ramp_info}")
        else:
            # Just show ramp info
            ticktext.append(ramp_info)
    
    # Set layout with minimal properties
    layout = {
        'barmode': 'overlay',
        'title': "Operations by Plant",
        'xaxis': {
            'title': 'Time',
            'tickvals': list(range(6, 19)),
            'ticktext': [f"{h:02d}:00" for h in range(6, 19)],
            'range': [6, 18],
            'gridcolor': 'lightgray',
            'gridwidth': 1
        },
        'yaxis': {
            'tickvals': tickvals,
            'ticktext': ticktext,
            'tickfont': {'size': 12},
            'categoryorder': 'array',
            'categoryarray': y_values
        },
        'margin': {'l': 180, 'r': 20, 't': 50, 'b': 40},
        'plot_bgcolor': 'white',
        'height': max(600, 40 * len(y_values) + 100),
        'showlegend': False,
        'bargap': 0.15
    }
    
    fig.update_layout(**layout)
    
    # Add plant separators - only for adjacent plants
    current_plant = None
    for i, y_val in enumerate(y_values):
        plant_name = y_val.split(' - ')[0]
        
        if plant_name != current_plant and current_plant is not None:
            # Add separator
            fig.add_shape(
                type="rect",
                x0=5.9,
                x1=18.1,
                y0=i - 0.5,
                y1=i - 0.2,
                fillcolor="rgba(220,220,220,0.5)",
                line=dict(color="rgba(0,0,0,0)", width=0),
            )
        
        current_plant = plant_name
    
    # Only add current time line if within view range
    now = datetime.now()
    current_hour = now.hour + now.minute / 60
    if 6 <= current_hour <= 18:
        fig.add_shape(
            type="line",
            x0=current_hour,
            y0=0,
            x1=current_hour,
            y1=1,
            yref="paper",
            line=dict(color="red", width=2),
        )
        
        fig.add_annotation(
            x=current_hour,
            y=1.01,
            yref="paper",
            text=f"Now: {now.strftime('%H:%M')}",
            showarrow=False,
            font=dict(color="red", size=10),
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="red",
            borderwidth=1
        )
    
    return fig

def empty_figure(message="No data available"):
    """
    Create an empty figure with a message.
    
    Args:
        message (str): Message to display
        
    Returns:
        go.Figure: Empty Plotly figure
    """
    fig = go.Figure()
    
    fig.update_layout(
        title="Operations by Plant",
        xaxis=dict(
            title='Time',
            tickvals=list(range(6, 19)),
            ticktext=[f"{h:02d}:00" for h in range(6, 19)],
            range=[6, 18],
            showgrid=True,
            gridcolor='lightgray',
            gridwidth=1
        ),
        yaxis=dict(
            title='Plant - Ramp',
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        annotations=[
            dict(
                text=message,
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=18)
            )
        ],
        plot_bgcolor='white',
        height=600
    )
    
    return fig