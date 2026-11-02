from app.service_pricing import calculate_color_pricing


# Search-index snapshot consulted 2026-11-02; not a live pricing feed.
BUCLES_SOURCE_URL = 'https://www.bucles.com.ar/servicios/'
BUCLES_REFERENCE_DATE = '2026-11-02'
BUCLES_COLOR_EXAMPLES = (
    ('corto', 'Color - corto (ejemplo Bucles)', 39999),
    ('melena', 'Color - melena (ejemplo Bucles)', 44999),
    ('largo', 'Color - largo (ejemplo Bucles)', 49999),
    ('extralargo', 'Color - extralargo (ejemplo Bucles)', 54999),
    ('abundante', 'Color - extralargo abundante (ejemplo Bucles)', 59999),
    ('aplicacion', 'Solo aplicacion (ejemplo Bucles)', 19999),
)


def bucles_color_examples():
    for length, name, price in BUCLES_COLOR_EXAMPLES:
        yield name, calculate_color_pricing({
            'kind': 'aplicacion' if length == 'aplicacion' else 'completo',
            'length': 'todos' if length == 'aplicacion' else length,
            'materials': [], 'labour': 0, 'overhead': 0, 'other_costs': 0,
            'margin': 0, 'costs_confirmed': False, 'reference_price': price,
            'example_key': f'bucles-color-20261102-{length}',
        })
