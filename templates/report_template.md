## SBA Account
- **ULP Environment:** 
    - 504: {{ data.ulp['504'] }}
    - 502: {{ data.ulp['502'] }}
    - OOM: {{ data.ulp['oom'] }}
- **CLS-Prod Environment:**
    - 504: {{ data.cls['504'] }}
    - 502: {{ data.cls['502'] }}
    - OOM: {{ data.cls['oom'] }}
- **FileMover Failed Jobs:** {{ data.ulp['fm_failures']['num_total_failures'] }} total failures, {{ data.ulp['fm_failures']['num_distinct_failures'] }} distinct failures
{%- for name, failure in data.ulp['fm_failures']['jobs'].items() %}
    - {{ name }}: {{ failure["count"] }}{% if failure["recent_success"] %}, succeeded on most recent attempt{% endif %}
{%- endfor %}

    
## LOS Account
- 504: {{ data.los['504'] }}
- 502: {{ data.los['502'] }}

## OSC Account
- Synthetic Test Failures: 
    - core.allocore.com: {{ data.ulp["allocore"] }}
    - urifinvest.com: {{ data["stg-core"]["urifinvest"]}}
- Sentry:
    - Failed Backend Rates: {{ data.osc_failed_backend }}
    - Unusual P95 scores: {{ data.osc_p95 }}