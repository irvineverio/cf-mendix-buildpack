import logging
import os

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

try:
    from buildpack.runtime_components.metrics import BaseMetricsEmitterThread
except:
    class BaseMetricsEmitterThread():
        pass

    logging.exception("Failed to load Metrics dependency, openmetrics not available")

class DummyMetricsEmitterThread(BaseMetricsEmitterThread):
    def __init__(self, interval, m2ee):
        # don't call super class init to avoid actual emitter initialization
        # because we don't emit anything but want to re-use internal functions
        #super().__init__()
        self.interval = interval
        self.m2ee = m2ee
        self.db = None

    def _gather_metrics(self):
        stats = {}
        for inject_method in self._select_stats_to_emit:
            stats = inject_method(stats)
        return stats

    @property
    def _select_stats_to_emit(self):
        selected_stats = [
            #self._inject_database_stats,
            #self._inject_storage_stats,
            self._inject_health,
        ]
        selected_stats.append(self._inject_m2ee_stats)
        return selected_stats


class OpenMetrics(BaseHTTPRequestHandler):

    CONTENT_TYPE = str('application/openmetrics-text; version=1.0.0; charset=utf-8')

    def _send_response(self, data, status=200):
            self.send_response(status)
            self.send_header("Content-Type", self.CONTENT_TYPE)
            self.send_header("Content-length", len(data))
            self.end_headers()

            if data:
                self.wfile.write(bytes(data, "utf-8"))
                self.wfile.flush()

    def do_GET(self):
        try:
            if self.path == "/metrics":
                metrics = []
                metrics.extend(self._get_metrics())
                self._send_response("".join(metrics))
            else:
                self._send_response(None, status=404)
        except Exception as e:
            logging.exception("OpenMetrics general error", e)

    def _get_metrics(self):
        try:
            mendix_metrics = DummyMetricsEmitterThread(interval=1, m2ee=self.server.m2ee)
            stats = mendix_metrics._gather_metrics()
        except Exception as e:
            logging.exception("OpenMetrics error gathering metrics", e)
            stats = {}
            #stats = {'database': {'indexes_size': 1998848, 'tables_size': 11436911, 'xact_commit': 16712, 'xact_rollback': 7, 'tup_inserted': 4297, 'tup_updated': 203, 'tup_deleted': 5, 'tcp_latency': '0.78'}, 'storage': {'get_number_of_files': 0}, 'health': {'health': 7, 'diagnosis': '', 'response': {'feedback': {'health': 'unknown'}, 'result': 0}}, 'mendix_runtime': {'sessions': {'user_sessions': {}, 'named_users': 4, 'anonymous_sessions': 0, 'named_user_sessions': 0}, 'cache': {'total_count': 0}, 'memory': {'used_nonheap': 117452288, 'init_nonheap': 7667712, 'max_nonheap': 780140544, 'committed_nonheap': 125919232, 'init_heap': 536870912, 'memorypools': [{'is_heap': False, 'usage': 1247104, 'name': "CodeHeap 'non-nmethods'", 'index': 0}, {'is_heap': False, 'usage': 87787976, 'name': 'Metaspace', 'index': 1}, {'is_heap': False, 'usage': 12541824, 'name': "CodeHeap 'profiled nmethods'", 'index': 2}, {'is_heap': False, 'usage': 12776776, 'name': 'Compressed Class Space', 'index': 3}, {'is_heap': True, 'usage': 15728640, 'name': 'G1 Eden Space', 'index': 4}, {'is_heap': True, 'usage': 39891968, 'name': 'G1 Old Gen', 'index': 5}, {'is_heap': True, 'usage': 8388608, 'name': 'G1 Survivor Space', 'index': 6}, {'is_heap': False, 'usage': 3098368, 'name': "CodeHeap 'non-profiled nmethods'", 'index': 7}], 'committed_heap': 536870912, 'max_heap': 536870912, 'used_heap': 64009216, 'code': 16887296, 'permanent': 87787976, 'eden': 15728640, 'survivor': 8388608, 'tenured': 39891968, 'nativecode': 20111360, 'jar': 0, 'javaheap': 472861696, 'codecache': 16887296, 'nativemem': 196739072, 'other': 0, 'stacks': 4440064, 'total': 426938368}, 'languages': ['en_US'], 'entities': 64, 'requests': {'': 0, 'ws/': 0, 'file': 0, 'ws-doc/': 0, 'manifest.webmanifest': 0, 'api-doc/': 0, 'api/': 0, 'rest-doc/': 0, 'odata-doc/': 0, 'xas/': 0, 'p/': 0}, 'connectionbus': {'select': 93, 'insert': 1, 'update': 3, 'delete': 0, 'transaction': 38}, 'jetty': {'current_connections': 0, 'max_connections': 0, 'idle_timeout': 30000, 'connected_end_points': 0, 'max_idle_time_s': 30, 'requests_active_max': 0}, 'threadpool': {'idle_threads': 6, 'stop_timeout': 30000, 'queue_size': 0, 'max_threads': 254, 'threads_priority': 5, 'threads': 8, 'max_queued': 0, 'idle_timeout': 60000, 'min_threads': 8, 'max_idle_time_s': 60, 'max_stop_time_s': 30, 'threadpool_size': 8, 'active_threads': 2}, 'threads': 50, 'critical_logs_count': 0}}

        metrics = []
        for (name, labels, value) in flatten(stats):
            metrics.append(self._single_metric(name=name, labels=labels, value=value))
        metrics.append("# EOF\n")
        return metrics

    def _single_metric(self, help="Not yet defined", type="gauge", name="unnamed", labels={}, value=0):
        labels_string = ""
        if labels:
            components = []
            for tag_name, tag_value in labels.items():
                # ensure string and sanitize
                tag_value = str(tag_value).replace('"', '').replace("\n", "-")
                tag_name = tag_name.replace('"', '').replace("\n", "-")

                components.append(f"{tag_name}=\"{tag_value}\"")
            labels_string_inner = ",".join(components)
            labels_string = f"{{{labels_string_inner}}}"
        # ref: https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md
        return f"""# HELP {name} {help}
# TYPE {name} {type}
{name}{labels_string} {value}
"""


def flatten(d, sep="_"):
    import collections
    result = []

    def recurse(t, parent_key="", labels=None):
        if isinstance(t, list):
            if parent_key == "mendix_runtime_memory_memorypools":
                for i in range(len(t)):
                    labels = {
                        "name": t[i]['name'],
                        "is_heap": t[i]['is_heap'],
                    }
                    v = t[i]['usage']
                    result.append((parent_key, labels, v))
            else:
                for i in range(len(t)):
                    recurse(t[i], parent_key + sep + str(i) if parent_key else str(i), labels=labels)
        elif isinstance(t, dict):
            if parent_key == "mendix_runtime_requests":
                for k,v in t.items():
                    # rewrite empty string to wildcard for usability
                    if k == "":
                        k = "*"
                    recurse(v, parent_key if parent_key else k, labels={"path": k})
            else:
                for k,v in t.items():
                    recurse(v, parent_key + sep + k if parent_key else k, labels=labels)
        else:
            if type(t) == int or type(t) == float:
                result.append((parent_key, labels, t))
    recurse(d)
    return result

def _start_server(m2ee, port):
    httpd = HTTPServer(('', port), OpenMetrics)
    httpd.m2ee = m2ee
    httpd.serve_forever()

def run(m2ee, port=8080):
    if os.environ.get("OPENMETRICS_ENABLED", "false").lower() != "true":
        return

    logging.info("Starting openmetrics service at port %d", port)
    daemon = threading.Thread(name='openmetrics',
                            target=_start_server,
                            args=(m2ee, port,))
    daemon.setDaemon(True) # Set as a daemon so it will be killed once the main thread is dead.
    daemon.start()