from cloudify_cli.logger import get_global_json_output


BASE_SUMMARY_FIELDS = [
    'tenant_name',
    'visibility',
]


def structure_summary_results(results, target_field, sub_field,
                              summary_type):
    """Restructure the results returned from the rest client.

    This is needed in case sub-fields are provided, as sub-fields will result
    in output that looks like:
    [
        {
            "<target_field>": "<value>",
            "<summary_type>": <total count>,
            "by <sub_field>": [
                {
                    "<sub_field>": "<sub_field value>",
                    "<summary_type>": <count>,
                },
                ... more sub-field results for this value of target_field ...
            ],
        },
        ... more results ...
    ]

    For compatibility with the CLI output tools, we want to turn this into:
    [
        {
            "<target_field>": "<value>",
            "<sub_field>": "<sub_field value>",
            "<summary_type>": <count>,
        },
        ... more sub-field results for this value of target_field ...
        {
            "<target_field>": "<value>",
            "<sub_field>": "<TOTAL if not json, empty if json>",
            "<summary_type>": <count>,
        },
        ... sub-fields followed by totals for other target_field values ...
    ]
    """
    if sub_field:
        columns = [target_field, sub_field, summary_type]
        structured_result = []
        for result in results:
            for sub_result in result['by ' + sub_field]:
                structured_result.append(
                    {
                        target_field: result[target_field],
                        sub_field: sub_result[sub_field],
                        summary_type: sub_result[summary_type],
                    }
                )
            structured_result.append(
                {
                    target_field: result[target_field],
                    sub_field: None if get_global_json_output() else 'TOTAL',
                    summary_type: result[summary_type],
                }
            )
    else:
        columns = [target_field, summary_type]
        structured_result = results
    return columns, structured_result
