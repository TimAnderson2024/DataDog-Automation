{%- for env in data %}
## {{ env.env }}
{%- if env._errs is defined and env._errs %}
{%- for err_type, result in env._errs.items() %}
- **{{ err_type }}**: {{ result.aggregate }}
{%- endfor %}
{%- endif %}
{%- if env.event_results is defined and env.event_results %}
{%- for event, result in env.event_results.items() %}
- **{{ event }}**: {{ result.aggregate }}
{%- endfor %}
{%- endif %}
{%- if env.synthetic_results is defined and env.synthetic_results %}
{%- for test, result in env.synthetic_results.items() %}
- Synthetic test on `{{ result.name }}`: {{ result.failure_count }} failures in last 24hr
{%- endfor %}
{%- endif %}
{%- if env.log_results is defined and env.log_results %}
- Filemover: {{ env.log_results["failed_fm_jobs"].aggregate }} failures in last 24hr
{%- endif %}
{%- endfor %}