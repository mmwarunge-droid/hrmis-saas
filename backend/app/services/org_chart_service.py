"""Bounded, iterative presentation of authorized reporting relationships.

Never repairs persisted manager IDs. Missing/invalid edges become display roots.
"""


def build_org_chart(employees):
    people = {str(e.id): e for e in employees}
    parents = {}
    issues = []
    for key, employee in people.items():
        manager = str(employee.manager_id) if employee.manager_id else None
        if manager == key or (manager and manager not in people):
            issues.append({"employee_id": key, "code": "self_reporting" if manager == key else "manager_not_visible"})
            manager = None
        parents[key] = manager

    # Every employee has at most one parent: detect cycles in linear time.
    done = set()
    for start in people:
        path, positions = [], {}
        current = start
        while current is not None and current not in done:
            if current in positions:
                issues.append({"employee_id": current, "code": "reporting_cycle"})
                parents[current] = None
                break
            positions[current] = len(path)
            path.append(current)
            current = parents[current]
        done.update(path)

    nodes = {}
    for key, employee in people.items():
        department = employee.department
        # Defensive against legacy cross-tenant department foreign keys too.
        department = department if department and department.tenant_id == employee.tenant_id else None
        manager = people.get(parents[key])
        nodes[key] = {
            "id": key,
            "full_name": employee.full_name,
            "employee_number": employee.employee_number,
            "profile_photo_url": employee.profile_photo_url,
            "job_title": employee.job_title,
            "department_id": str(department.id) if department else None,
            "department_name": department.name if department else None,
            "manager_id": parents[key],
            "manager_name": manager.full_name if manager else None,
            "work_location": employee.work_location,
            "employment_status": employee.employment_status,
            "email": employee.email,
            "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
            "children": [],
            "direct_report_count": 0,
            "indirect_report_count": 0,
        }
    roots = []
    for key, node in nodes.items():
        if parents[key]:
            nodes[parents[key]]["children"].append(node)
        else:
            roots.append(node)
    order, stack = [], [(node, 1) for node in roots]
    max_depth = 0
    while stack:
        node, level = stack.pop()
        max_depth = max(max_depth, level)
        order.append(node)
        stack.extend((child, level + 1) for child in node["children"])
    for node in reversed(order):
        node["direct_report_count"] = len(node["children"])
        node["indirect_report_count"] = sum(
            c["direct_report_count"] + c["indirect_report_count"] for c in node["children"]
        )
    return {
        "roots": roots,
        "items": [{k: v for k, v in node.items() if k != "children"} for node in nodes.values()],
        "integrity_issues": issues,
        "meta": {
            "total": len(nodes),
            "root_count": len(roots),
            "manager_count": sum(bool(n["children"]) for n in nodes.values()),
            "max_depth": max_depth,
        },
    }
