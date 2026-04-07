{%- for env in data %}
*{{ env.env }}*
{%- if env._errs is defined and env._errs %}
{%- for err_type, result in env._errs.items() %}
- *{{ err_type }}*: {{ result.aggregate }}
{%- endfor %}
{%- endif %}
{%- if env.event_results is defined and env.event_results %}
{%- for event, result in env.event_results.items() %}
- *{{ event }}*: {{ result.aggregate }}
{%- endfor %}
{%- endif %}
{%- if env.synthetic_results is defined and env.synthetic_results %}
{%- for test, result in env.synthetic_results.items() %}
- Synthetic test on `{{ result.name }}`: {{ result.failure_count }} failures in last 24hr
{%- endfor %}
{%- endif %}
{%- if env.filtered_fm_jobs is defined and env.filtered_fm_jobs %}
*Filemover failures in last 24hr:*
{%- for failed_job, count in env.filtered_fm_jobs.items() %}
- `{{ failed_job }}:` {{ count }}
{%- endfor %}
{%- endif %}
{% endfor %}