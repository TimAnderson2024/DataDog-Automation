{%- for env in data %}
## {{ env.env }}
{%- if env._errs is defined and env._errs %}
{%- for err_type, result in env._errs.items() %}
- **{{ err_type }}**: {{ result.aggregate }}
{%- endfor %}
{%- endif %}

{%- if env.synthetic_tests is defined and env.synthetic_tests %}
{%- for test, result in env.synthetic_tests.items() %}
- Synthetic test on **{{ test }}**: {{ result.failure_count }} failures in last 24hr
{%- endfor %}
{%- endif %}
{%- endfor %}