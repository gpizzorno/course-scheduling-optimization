import base64
import io
from pathlib import Path

import dash_bootstrap_components as dbc
import flask
import pandas as pd
from dash import Dash, dash_table, dcc, html
from dash.dependencies import Input, Output
from scheduling import SchedulingOptimizer

external_stylesheets = [dbc.themes.SANDSTONE]

app = Dash(external_stylesheets=external_stylesheets, suppress_callback_exceptions=True)
app.title = 'Course Scheduling'
app.scripts.config.serve_locally = True

optimizer = SchedulingOptimizer()  # Initialize optimizer

# Initialize global variables to store data
FACULTY = None
COURSES = None
SELECTION = None

app.layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    html.H2('Course Scheduling', className='text-primary m-0'),
                    className='d-flex align-items-center',
                ),
                dbc.Col(
                    html.Img(src='/static/history-logo.png', height='50px'),
                    className='d-flex mr-l justify-content-end',
                ),
            ],
            className='mt-2 mb-4 pb-2 border-bottom',
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Label(
                                'Faculty data:',
                                html_for='upload-faculty',
                                width=5,
                                className='text-end',
                            ),
                            dbc.Col(
                                dcc.Upload(
                                    id='upload-faculty',
                                    children=dbc.Button(
                                        'Load Faculty Data',
                                        id='faculty_button',
                                        className='upload-button',
                                        color='primary',
                                    ),
                                ),
                            ),
                        ],
                    ),
                    width=3,
                ),
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Label(
                                'Course data:',
                                html_for='upload-courses',
                                width=5,
                                className='text-end',
                            ),
                            dbc.Col(
                                dcc.Upload(
                                    id='upload-courses',
                                    children=dbc.Button(
                                        'Load Course Data',
                                        id='courses_button',
                                        className='upload-button',
                                        color='primary',
                                    ),
                                ),
                            ),
                        ],
                    ),
                ),
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Label(
                                'Selection data:',
                                html_for='upload-selection',
                                width=5,
                                className='text-end',
                            ),
                            dbc.Col(
                                dcc.Upload(
                                    id='upload-selection',
                                    children=dbc.Button(
                                        'Load Selection Data',
                                        id='selection_button',
                                        className='upload-button',
                                        color='primary',
                                    ),
                                ),
                            ),
                        ],
                    ),
                    width=4,
                ),
                dbc.Col(
                    dbc.Button(
                        'Calculate',
                        id='calculate_button',
                        className='run-button align-self-end',
                        color='danger',
                    ),
                    className='d-flex justify-content-end',
                    width=2,
                ),
            ],
            className='py-4 border-bottom g-5 align-items-center',
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.CardBody(
                        [
                            html.H4('Faculty Data', className='card-title'),
                            html.Div(
                                id='faculty_data',
                                children=[
                                    html.Div(style={'display': 'none'}),
                                ],
                                className='mt-3',
                            ),
                        ],
                    ),
                    width=3,
                ),
                dbc.Col(
                    dbc.CardBody(
                        [
                            html.H4('Course Data', className='card-title'),
                            html.Div(
                                id='course_data',
                                children=[
                                    html.Div(style={'display': 'none'}),
                                ],
                                className='mt-3',
                            ),
                        ],
                    ),
                    width=3,
                ),
                dbc.Col(
                    dbc.CardBody(
                        [
                            html.H4('Selection Data', className='card-title'),
                            html.Div(
                                id='selection_data',
                                children=[
                                    html.Div(style={'display': 'none'}),
                                ],
                                className='mt-3',
                            ),
                        ],
                    ),
                    width=6,
                ),
            ],
            className='py-4 border-bottom',
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.CardBody(
                        [
                            html.H4('Results', className='card-title'),
                            html.Div(
                                id='results',
                                children=[
                                    html.Div(style={'display': 'none'}),
                                ],
                                className='mt-3',
                            ),
                        ],
                    ),
                ),
                dbc.Col(
                    dbc.CardBody(
                        [
                            html.H4('Log', className='card-title'),
                            html.Div(id='log_data', className='mt-3'),
                        ],
                    ),
                ),
            ],
            className='py-4',
        ),
        dbc.Row(
            dbc.Col(
                dbc.CardBody(
                    [
                        html.H4('Charts', className='card-title'),
                        html.Div(id='charts', className='mt-3'),
                    ],
                ),
            ),
            className='py-4 border-bottom',
        ),
    ],
    fluid=True,
    className='app-container',
)


def parse_contents(contents, filename, headers):
    """Parse uploaded file contents."""
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        if 'csv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), names=headers)
        elif 'xls' in filename:
            df = pd.read_excel(io.BytesIO(decoded), names=headers)
        else:
            return None, 'Unsupported file format'
    except Exception as e:  # noqa: BLE001
        return None, f'Error processing file: {e!s}'
    else:
        return df, None


@app.callback(
    [Output('results', 'children'), Output('log_data', 'children'), Output('charts', 'children')],
    [Input('calculate_button', 'n_clicks')],
)
def process_optimization(n_clicks):
    """Run optimization."""
    if n_clicks is None:
        return None, None, None

    # Check if course data is loaded
    if COURSES is not None and FACULTY is not None and SELECTION is not None:
        # # Prepare data for optimization
        if SELECTION.iloc[:, 0].dtype == 'object':  # First column is course names
            prep_sel = SELECTION.set_index(SELECTION.columns[0])

        # Run optimization
        try:
            results, error = optimizer.optimize_schedule(prep_sel, COURSES, FACULTY)
            if error:
                return html.Div(f'Optimization error: {error}', style={'color': 'red'}), None, None

            # Create results table
            results_table = dash_table.DataTable(
                data=results['results'],
                columns=[
                    {'name': 'Course', 'id': 'Course'},
                    {'name': 'Slot', 'id': 'Slot'},
                    {'name': 'Time', 'id': 'Time'},
                    {'name': 'Satisfaction', 'id': 'Satisfaction', 'type': 'numeric', 'format': {'specifier': '.2f'}},
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left'},
                sort_action='native',
                page_size=10,
            )

            # Create log
            log_content = dcc.Markdown(f"""
    **Optimization Results:**
    - Total Satisfaction: {results['satisfaction_total']:.1f}
    - Solve Time: {results['solve_time']} ms
    - MWF Courses: {results['stats']['mwf_count']}
    - TT Courses: {results['stats']['tt_count']}
    - Day Balance Difference: {results['stats']['balance_diff']} (limit: ≤2)
    - Time Balance Difference: {results['stats']['time_diff']} (limit: ≤2)

    **Constraint Compliance:**
    - Day Pattern Balance: {'✓' if results['stats']['balance_diff'] <= 2 else '✗'}
    - Start Time Balance: {'✓' if results['stats']['time_diff'] <= 2 else '✗'}
            """)  # noqa: PLR2004

            # Create charts
            charts = create_optimization_charts(results)

            return results_table, log_content, charts  # noqa: TRY300

        except Exception as e:  # noqa: BLE001
            return html.Div(f'Unexpected error: {e!s}', style={'color': 'red'}), None, None

    return html.Div('Please load all required data files before running optimization.'), None, None


def create_optimization_charts(results):
    """Create visualization charts for optimization results."""
    stats = results['stats']
    slot_counts = stats['slot_counts']

    # Chart 1: Courses per slot
    slot_chart = dcc.Graph(
        figure={
            'data': [
                {
                    'x': [f's{i + 1}' for i in range(len(slot_counts))],
                    'y': slot_counts,
                    'type': 'bar',
                    'marker': {
                        'color': ['#ff7f0e' if i in [0, 2, 4, 6, 8] else '#1f77b4' for i in range(len(slot_counts))],
                    },
                },
            ],
            'layout': {
                'title': {
                    'text': 'Courses per Time Slot',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16},
                },
                'xaxis': {
                    'title': {
                        'text': 'Time Slot',
                        'font': {'size': 14},
                    },
                },
                'yaxis': {
                    'title': {
                        'text': 'Number of Courses',
                        'font': {'size': 14},
                    },
                },
                'height': 400,
                'margin': {'l': 60, 'r': 40, 't': 60, 'b': 60},
                'showlegend': False,
            },
        },
    )

    # Chart 2: MWF vs TT distribution
    balance_chart = dcc.Graph(
        figure={
            'data': [
                {
                    'x': ['MWF', 'TT'],
                    'y': [stats['mwf_count'], stats['tt_count']],
                    'type': 'bar',
                    'marker': {
                        'color': ['#ff7f0e', '#1f77b4'],
                    },
                },
            ],
            'layout': {
                'title': {
                    'text': f'Day Pattern Balance (Diff: {stats["balance_diff"]})',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16},
                },
                'xaxis': {
                    'title': {
                        'text': 'Day Pattern',
                        'font': {'size': 14},
                    },
                },
                'yaxis': {
                    'title': {
                        'text': 'Number of Courses',
                        'font': {'size': 14},
                    },
                },
                'height': 400,
                'margin': {'l': 60, 'r': 40, 't': 60, 'b': 60},
                'showlegend': False,
            },
        },
    )

    # Chart 3: Start time distribution
    time_chart = dcc.Graph(
        figure={
            'data': [
                {
                    'x': list(stats['time_counts'].keys()),
                    'y': list(stats['time_counts'].values()),
                    'type': 'bar',
                    'marker': {'color': '#2ca02c'},
                },
            ],
            'layout': {
                'title': {
                    'text': f'Start Time Distribution (Diff: {stats["time_diff"]})',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16},
                },
                'xaxis': {
                    'title': {
                        'text': 'Start Time',
                        'font': {'size': 14},
                    },
                },
                'yaxis': {
                    'title': {
                        'text': 'Number of Courses',
                        'font': {'size': 14},
                    },
                },
                'height': 400,
                'margin': {'l': 60, 'r': 40, 't': 60, 'b': 60},
                'showlegend': False,
            },
        },
    )

    # Chart 4: Satisfaction histogram
    satisfaction_values = [r['Satisfaction'] for r in results['results']]
    satisfaction_chart = dcc.Graph(
        figure={
            'data': [
                {
                    'x': satisfaction_values,
                    'type': 'histogram',
                    'nbinsx': 20,
                    'marker': {'color': '#9467bd'},
                },
            ],
            'layout': {
                'title': {
                    'text': 'Distribution of Satisfaction Scores',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16},
                },
                'xaxis': {
                    'title': {
                        'text': 'Satisfaction Score',
                        'font': {'size': 14},
                    },
                },
                'yaxis': {
                    'title': {
                        'text': 'Number of Assignments',
                        'font': {'size': 14},
                    },
                },
                'height': 400,
                'margin': {'l': 60, 'r': 40, 't': 60, 'b': 60},
                'showlegend': False,
            },
        },
    )

    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(slot_chart, width=6),
                    dbc.Col(balance_chart, width=6),
                ],
            ),
            dbc.Row(
                [
                    dbc.Col(time_chart, width=6),
                    dbc.Col(satisfaction_chart, width=6),
                ],
            ),
        ],
    )


@app.callback(
    Output('faculty_data', 'children'),
    [Input('upload-faculty', 'contents'), Input('upload-faculty', 'filename')],
)
def faculty_data(contents, filename):  # noqa: D103
    if contents is not None:
        df, error = parse_contents(contents, filename, ['Name', 'Adjustment', 'Voting'])
        if df is not None:
            global FACULTY  # noqa: PLW0603
            FACULTY = df  # Store faculty data globally
            # Convert DataFrame to HTML table
            return html.Div(
                [
                    dash_table.DataTable(
                        data=df.to_dict('records'),
                        columns=[{'name': i, 'id': i} for i in df.columns],
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left'},
                        sort_action='native',
                        page_size=10,
                    ),
                ],
            )
        return html.Div(f'Error: {error}', style={'color': 'red'})
    return None


@app.callback(
    Output('course_data', 'children'),
    [Input('upload-courses', 'contents'), Input('upload-courses', 'filename')],
)
def course_data(contents, filename):  # noqa: D103
    if contents is not None:
        df, error = parse_contents(contents, filename, ['Course', 'Faculty'])
        if df is not None:
            global COURSES  # noqa: PLW0603
            COURSES = df
            # Convert DataFrame to HTML table
            return html.Div(
                [
                    dash_table.DataTable(
                        data=df.to_dict('records'),
                        columns=[{'name': i, 'id': i} for i in df.columns],
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left'},
                        sort_action='native',
                        page_size=10,
                    ),
                ],
            )
        return html.Div(f'Error: {error}', style={'color': 'red'})
    return None


@app.callback(
    Output('selection_data', 'children'),
    [Input('upload-selection', 'contents'), Input('upload-selection', 'filename')],
)
def selection_data(contents, filename):  # noqa: D103
    if contents is not None:
        df, error = parse_contents(
            contents,
            filename,
            ['Course', 's1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10'],
        )
        global SELECTION  # noqa: PLW0603
        SELECTION = df
        # Convert DataFrame to HTML table
        return html.Div(
            [
                dash_table.DataTable(
                    data=df.to_dict('records'),
                    columns=[{'name': i, 'id': i} for i in df.columns],
                    style_table={'overflowX': 'auto', 'overflowY': 'scroll'},
                    style_cell={'textAlign': 'left'},
                    sort_action='native',
                    page_size=10,
                ),
            ],
        )
        return html.Div(f'Error: {error}', style={'color': 'red'})
    return None


@app.callback(Output('faculty_button', 'children'), [Input('upload-faculty', 'filename')])
def update_faculty_button(filename):  # noqa: D103
    if filename is not None:
        return filename
    return 'Load Faculty Data'


@app.callback(Output('courses_button', 'children'), [Input('upload-courses', 'filename')])
def update_courses_button(filename):  # noqa: D103
    if filename is not None:
        return filename
    return 'Load Course Data'


@app.callback(Output('selection_button', 'children'), [Input('upload-selection', 'filename')])
def update_selection_button(filename):  # noqa: D103
    if filename is not None:
        return filename
    return 'Load Selection Data'


image_directory = Path.cwd() / 'app' / 'assets'
list_of_images = ['history-logo.png']
static_image_route = '/static/'


@app.server.route(f'{static_image_route}<image>')
def serve_image(image):  # noqa: D103
    if image not in list_of_images:
        msg = f'"{image}" is excluded from the allowed static files'
        raise Exception(msg)  # noqa: TRY002
    return flask.send_from_directory(image_directory, image)


if __name__ == '__main__':
    app.run(debug=True)
