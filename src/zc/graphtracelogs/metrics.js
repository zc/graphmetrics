dojo.require("dijit.ColorPalette");
dojo.require("dijit.Dialog");
dojo.require("dijit.form.Button");
dojo.require("dijit.form.CheckBox");
dojo.require("dijit.form.DateTextBox");
dojo.require("dijit.form.FilteringSelect");
dojo.require("dijit.form.TextBox");
dojo.require("dijit.form.TimeTextBox");
dojo.require("dijit.layout.BorderContainer");
dojo.require("dijit.layout.ContentPane");
dojo.require("dijit.Menu");
dojo.require("dijit.Tooltip");
dojo.require("dojo.data.ItemFileReadStore");
dojo.require("dojo.data.ItemFileWriteStore");
dojo.require("dojo.date.stamp");
dojo.require("dojox.grid.DataGrid");

dojo.addOnLoad(function() {
    var imgid = 0;
    var series;
    var charts = {};

    var update_on_resize = function () {
        for (var i in charts)
            charts[i].update();
    };
    dojo.connect(window, 'onresize', update_on_resize);

    var keep_refreshing = function () {
        for (var i in charts) {
            charts[i].refresh();
        }
        setTimeout(keep_refreshing, 60000);
    };
    setTimeout(keep_refreshing, 60000);

    var twodigits = function (i) {
        var result = i.toString();
        if (result.length < 2)
            result = '0' + i;
        return result;
    };
    var date2string = function (d) {
        if (d)
            return (d.getFullYear()
                    + '-' + twodigits(d.getMonth()+1)
                    + '-' + twodigits(d.getDate())
                   );
        return undefined;
    };
    var string2date = function (s) {
        if (s)
            return dojo.date.stamp.fromISOString(s);
        return undefined;
    };
    var time2string = function (d) {
        if (d)
            return ('T'
                    + d.getHours()
                    + ':' + twodigits(d.getMinutes())
                    + ':' + twodigits(d.getSeconds())
                   );
        return undefined;
    };
    var string2time = function (s) {
        if (s) {
            var result = new Date();
            s = s.split('T')[1].split(':');
            result.setHours(s[0]);
            result.setMinutes(s[1]);
            result.setSeconds(s[2]);
            return result;
        }
        return undefined;
    };

    var DateTimeUI = function (div, params, name, update) {
        var date_widget = new dijit.form.DateTextBox({
            value: string2date(params[name]),
            onChange: function(date) {
                params[name] = date2string(date);
                update();
            }
        });
        div.appendChild(date_widget.domNode);
        dojo.style(div.lastChild, "width", "12ch");
        dojo.place('<span>T</span>', div)
        var time_widget = new dijit.form.TimeTextBox({
            value: string2time(params[name+'_time']),
            onChange: function(time) {
                params[name+'_time'] = time2string(time);
                update();
            }
        });
        div.appendChild(time_widget.domNode);
        dojo.style(div.lastChild, "width", "10ch");

        this.update = function (settings) {
            date_widget.attr('value', string2date(settings[name]) || null);
            time_widget.attr('value',
                             string2time(settings[name+'_time']) || null);
        };
    };

    var tooltip = function (node, text) {
        new dijit.Tooltip({connectId: [node], label: text});
    };

    var TextUI = function (
        div, label, params, name, update, length, regex, tip) {
        var widget = new dijit.form.ValidationTextBox({
            value: params[name],
            maxLength: length,
            regExp: regex,
            style: 'width: ' + (length+3) + 'ch',
            onChange: function(val) {
                params[name] = val;
                update();
            }
        });
        dojo.place('<span> '+label+': </span>', div);
        div.appendChild(widget.domNode);
        if (tip)
            tooltip(widget.domNode, tip);
        this.update = function (settings) {
            widget.attr('value', settings[name] || null);
        };
    };

    var BoolUI = function (div, label, params, name, update) {
        var widget = new dijit.form.CheckBox({
            checked: params[name] == 'y' ? 'checked': undefined,
            onChange: function(val) {
                if (val)
                    params[name] = 'y';
                else
                    params[name] = undefined;
                update();
            }
        });
        dojo.place('<span> '+label+': </span>', div)
        div.appendChild(widget.domNode);

        this.update = function (settings) {
            widget.attr('checked',
                        settings[name] == 'y' ? 'checked': undefined);
        };
    };

    var MySelect = dojo.declare(dijit.form.FilteringSelect, {
        _startSearchFromInput: function(){
            this.__last_search_value = this.focusNode.value;
	    this._startSearch(this.focusNode.value);
	},
        __last_search_value: ''
    });

    var seriesSelectUI = function (node, callback) {
        dojo.place(
            '<span style="font-size: large; font-weight: bold">'+
            'Start here! -&gt;</span>',
                   node);
        var select = new MySelect({
            searchAttr: 'id',
            store: series,
            queryExpr: '*${0}*',
            autoComplete: false,
            searchDelay: 300,
            onChange: function (v) {
                if (v)
                    callback(v);
                select.reset();
            }
        });
        node.appendChild(select.domNode);
        tooltip(select.domNode, 'search string using * for wildcards');
        node.appendChild(new dijit.form.Button({
            label: 'last search',
            onClick: function () {
                if (select.__last_search_value) {
                    select._abortQuery();
                    select.attr('displayedValue',
                                select.__last_search_value);
                    select._startSearch(select.__last_search_value);
                }
            }
        }).domNode);
    };

    var newContentPane = function(args, setup) {
        var pane = new dijit.layout.ContentPane(args);
        setup(pane.containerNode);
        return pane;
    };

    var seriesDialog = (function() {
        var dialog, _callback, store;

        var build_dialog = function () {
            var border = new dijit.layout.BorderContainer({
                gutters: false,
                style: 'width: 100%; height: 99%'
            });
            dialog = new dijit.Dialog({
                title:
                'Select one (or more agregated) series to define a plot data.',
                style: 'width: 640px; height: 300px',
                content: border
            });
            store = new dojo.data.ItemFileWriteStore({
                data: {
                    identifier: 'id',
                    items: []
                }
            });
            dojo.connect(dialog, 'hide', store, 'revert');
            border.addChild(newContentPane({
                style: 'height: 5ex; width: 100%',
                region:  'top'
            }, function (node) {
                seriesSelectUI(node, function (v) {
                    store.fetchItemByIdentity({
                        identity: v,
                        onItem: function (item) {
                            if (item)
                                alert("The series is already selected.")
                            else
                                store.newItem({id: v});
                        },
                        onError: alert
                    });
                });
            }));
            var grid = new dojox.grid.DataGrid({
                store: store,
                style: 'width: 100%; height: 100%',
                // query: {id: '*'},
                structure: [{
                    field: 'id',
                    name: 'Series name (metrics element)',
                    width: '100%'
                }]
            });
            border.addChild(
                new dijit.layout.ContentPane({
                    content: grid,
                    style: 'width: 100%',
                    region:  'center'
                })
            );
            border.addChild(newContentPane({
                style: 'height: 9ex; width: 100%',
                region: 'bottom'
            }, function (node) {
                node.appendChild(new dijit.form.Button({
                    label: 'Cancel',
                    onClick: function () {
                        dialog.hide();
                    }
                }).domNode);
                node.appendChild(new dijit.form.Button({
                    label: 'OK',
                    onClick: function () {
                        store.fetch({
                            onComplete: function (items) {
                                _callback(dojo.map(items, function (item) {
                                    return store.getValue(item, 'id');
                                }).join(','));
                                dialog.hide();
                            }
                        });
                    }
                }).domNode);
                node.appendChild(new dijit.form.Button({
                    label: '-',
                    style: 'float: right',
                    onClick: function () {
                        if (grid.selection.selectedIndex >= 0)
                            store.deleteItem(
                                grid.getItem(grid.selection.selectedIndex));
                    }
                }).domNode);
            }));
            border.startup();
            border.layout();
            grid.startup();
        };

        // Entry point
        return function (callback) {
            if (dialog == undefined)
                build_dialog();
            _callback = callback;
            dialog.show();
        }
    })();

    var plotDialog = (function () {
        var dialog, _callback, store, params = {title: ''};
        var title_ui;

        var build_dialog = function () {
            var border = new dijit.layout.BorderContainer({
                gutters: false,
                style: 'width: 100%; height: 99%'
            });
            dialog = new dijit.Dialog({
                title: 'Plots for this chart',
                style: 'width: 640px; height: 300px',
                autofocus: false,
                content: border
            });
            store = new dojo.data.ItemFileWriteStore({
                data: { items: [] }
            });
            dojo.connect(dialog, 'hide', store, 'revert');

            border.addChild(newContentPane({
                style: 'width: 100%; height: 4ex',
                region:  'top'
            }, function (node) {
                title_ui = new TextUI(node, 'Chart title', params, 'title',
                                      function () {}, 50, '.*');
            }));

            var grid = new dojox.grid.DataGrid({
                store: store,
                style: 'width: 100%; height: 100%',
                structure: [
                    {
                        field: 'legend',
                        name: 'Legend',
                        width: '10em',
                        editable: 'true'
                    },
                    {
                        field: 'color',
                        name: 'Color',
                        width: '5ch',
                        formatter: function (v, rowindex) {
                            v = v || '#000000';
                            var button = new dijit.form.Button({
                                onClick: function () {
                                    var dialog = new dijit.Dialog({
                                        content: new dijit.ColorPalette({
                                            palette: "7x10",
                                            onChange: function(v) {
                                                store.setValue(
                                                    grid.getItem(rowindex),
                                                    'color', v);
                                                dojo.style(
                                                    button.containerNode,
                                                    'backgroundColor', v);
                                                dialog.hide();
                                            }
                                        })
                                    });
                                    dojo.connect(
                                        dialog, 'hide', dialog,
                                        'destroyRecursive');
                                    dialog.show()
                                }
                            });
                            dojo.style(button.containerNode, 'height', '2ex');
                            dojo.style(button.containerNode, 'width', '1ch');
                            dojo.style(button.containerNode,
                                                     'backgroundColor', v);
                            return button;
                        }
                    },
                    {
                        field: 'data',
                        width: 'auto',
                        name: 'Series',
                        formatter: function (v) {
                            return v ? v.split(',').join('<br />') : '';
                        }
                    }
                ],
            });

            border.addChild(new dijit.layout.ContentPane({
                content: grid,
                style: 'width: 100%',
                region:  'center'
            }));


            border.addChild(newContentPane({
                style: 'width: 100%; height: 9ex',
                region:  'bottom'
            }, function (node) {
                node.appendChild(new dijit.form.Button({
                    label: 'Cancel',
                    onClick: function () { dialog.hide(); }
                }).domNode);
                node.appendChild(new dijit.form.Button({
                    label: 'OK',
                    onClick: function () {
                        store.fetch({
                            onComplete: function (items) {
                                _callback(
                                    params.title,
                                    dojo.map(items, function (item) {
                                        return {
                                            legend: store.getValue(item,
                                                                   'legend'),
                                            color: store.getValue(item,
                                                                  'color'),
                                            data: store.getValue(item, 'data')
                                        };
                                    }));
                                dialog.hide();
                            }
                        });
                    }
                }).domNode);

                var default_colors = [
                    "#000000", "#0000ff", "#ff0000", "#dda0dd",
                    "#800080", "#7fff00", "#6495ed", "#ffff00"]

                var newPlotItem = function (v) {
                    store.fetch({
                        onComplete: function (items) {
                            store.newItem({
                                legend: '',
                                color: default_colors[
                                    items.length % default_colors.length],
                                data: v
                            })
                        }
                    });
                }

                var select_div = dojo.create(
                    'div', {style: 'float: right'}, node);
                seriesSelectUI(select_div, newPlotItem);
                select_div.appendChild(new dijit.form.Button({
                    label: 'A',
                    onClick: function () {
                        seriesDialog(newPlotItem);
                    }
                }).domNode);
                tooltip(select_div.lastChild, 'aggregate multiple series');
                select_div.appendChild(new dijit.form.Button({
                    label: '-',
                    onClick: function () {
                        if (grid.selection.selectedIndex >= 0)
                            store.deleteItem(
                                grid.getItem(grid.selection.selectedIndex));
                    }
                }).domNode);
            }));

        }; // build_dialog

        // Entry point
        return function (title, items, callback) {
            if (dialog == undefined)
                build_dialog();
            _callback = callback;
            params.title = title
            dialog.show();
            title_ui.update(params);
            for (i = 0; i < items.length; i++) {
                store.newItem(items[i]);
            }
        }

    })();

    var plotdata2plotparams = function (data, params) {
        // update paramters with plot definitions from data array

        if (params) {
            // First clean out old
            var n = -1;
            for (var i in params) {
                if (i.slice(0, 4) == 'data')
                    n = Math.max(n, i.slice(4));
            }
            for (var i=0; i <= n; i++) {
                delete params['legend'+i];
                delete params['color'+i];
                delete params['data'+i];
            }
        } else
            params = {}

        // now update
        for (var i=0; i < data.length; i++) {
            params['legend'+i] = data[i].legend;
            params['color'+i] = data[i].color.slice(1);
            params['data'+i] = data[i].data;
        }
        return params;
    }

    var plotparams2plotdata = function (params) {
        // Cmpute a data array from plot params
        var n = -1;
        for (var i in params) {
            if (i.slice(0, 4) == 'data')
                n = Math.max(n, i.slice(4));
        }
        data = []
        for (var i=0; i <= n; i++) {
            data.push({
                legend: params['legend'+i],
                color:  '#'+params['color'+i],
                data: params['data'+i]
            });
        }
        return data;
    }

    var Chart = function (params) {
        var div = dojo.create('div',{}, dojo.body());
        params.bust = (new Date()).toString();
        params.width = div.clientWidth;
        if (params.imgid)
            imgid = Math.max(params.imgid, imgid);
        else {
            imgid++;
            params.imgid = imgid;
        }
        var img = dojo.create(
            'img', {id: 'img'+imgid,
                    src: 'show.png?'+dojo.objectToQuery(params)}, div);
        var update = function (ob) {
            if (ob != undefined)
                dojo.mixin(params, ob);
            params.bust = (new Date()).toString();
            params.width = div.clientWidth;
            img.src =  'show.png?'+dojo.objectToQuery(params);
        };
        this.update = update;
        var changed = function (ob) {
            params.generation = (params.generation || 0) + 1;
            update(ob);
        }

        this.refresh = function () {
            if (! params.end && ! params.end_time)
                update();
        };

        dojo.create('br', {}, div);
        div.appendChild(new dijit.form.Button({
            label: 'Reload',
            onClick: update
        }).domNode);

        var uis = [];
        this.update_settings = function (settings) {
            for (var i=0; i < uis.length; i++)
                uis[i].update(settings);
            changed(settings);
        };

        uis.push(new DateTimeUI(div, params, 'start', changed));
        dojo.place('<span> to </span>', div)
        uis.push(new DateTimeUI(div, params, 'end', changed));

        uis.push(new TextUI(div, 'Trail', params, 'trail', changed,
                            3, "^[0-9]+$",
                            'Trailing hours to show (ignoring time range)'));
        uis.push(new TextUI(div, 'Step', params, 'step', changed,
                            4, "[0-9]+"));
        uis.push(new TextUI(div, 'Min', params, 'lower_limit', changed,
                            6, "[0-9]+"));
        uis.push(new TextUI(div, 'Max', params, 'upper_limit', changed,
                            9, "[0-9]+"));
        uis.push(new BoolUI(div, 'Log', params, 'log', changed));

        // Apply same scaling
        div.appendChild(new dijit.form.Button({
            label: 'A',
            onClick: function () {
                var settings = {};
                dojo.forEach([
                    'start', 'start_time', 'end', 'end_time', 'trail', 'step',
                    'lower_limit', 'upper_limit', 'log'
                ], function (name) {
                    if (params[name])
                        settings[name] = params[name];
                });
                for (var i in charts) {
                    if (i != params.imgid)
                        charts[i].update_settings(settings);
                }
            }
        }).domNode);
        tooltip(div.lastChild, 'Apply this scaling to all charts');

        // Select data to show
        div.appendChild(new dijit.form.Button({
            label: "Contents",
            onClick: function () {
                plotDialog(
                    params.title, plotparams2plotdata(params),
                    function(title, data) {
                        params.title = title
                        plotdata2plotparams(data, params);
                        changed();
                    });
            }
        }).domNode);

        dojo.place('<span> Height: </span>', div)
        div.appendChild(new dijit.form.ValidationTextBox({
            value: params.height,
            maxLength: 4,
            regExp: "[0-9]+",
            onChange: function(val) {
                changed({height: val});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "7ch");

        div.appendChild(new dijit.form.Button({
            label: '-',
            style: 'float: right',
            onClick: function () {
                dojo.xhrPost({
                    url: 'destroy',
                    postData: 'imgid='+params.imgid,
                    load: function () {
                        dojo.destroy(div);
                        delete charts[params['imgid']];
                    },
                    error: function (error) {alert(error)}
                });

            }
        }).domNode);
        tooltip(div.lastChild, 'Remove this chart.');

        charts[params.imgid] = this;
    };

    var button_div = dojo.create('div',{}, dojo.body());
    var save_dialog = new dijit.Dialog({
        title: 'Save as:',
        style: 'width: 20em'
    });
    var save_name;
    save_dialog.containerNode.appendChild(
        new dijit.form.ValidationTextBox({
            regExp: "[0-9a-zA-z_.-]+",
            onChange: function (val) { save_name = val; }
        }).domNode);
    save_dialog.containerNode.appendChild(new dijit.form.Button({
        label: 'Cancel',
        onClick: function () { save_dialog.hide(); }
    }).domNode);
    save_dialog.containerNode.appendChild(new dijit.form.Button({
        label: 'OK',
        onClick: function() {
            save_dialog.hide();
            if (! save_name)
                return;
            dojo.xhrPost({
                url: 'save.json',
                postData: 'name='+save_name,
                handleAs: 'json',
                load: function (data) {
                    if (data.exists) {
                        if (confirm('Overwrite '+save_name+'?')) {
                            dojo.xhrPost({
                                url: 'save.json',
                                postData: dojo.objectToQuery({
                                    name: save_name,
                                    overwrite: 'y',
                                }),
                                handleAs: 'json',
                                load: function (data) {
                                    window.location.assign(
                                        data.url);
                                }
                            });
                        }
                    }
                    else
                        window.location.assign(data.url);
                },
                error: function (error) {alert(error)}
            });
        }
    }).domNode);

    var savedMenuButton = function(saved) {
        var menu = new dijit.Menu({ style: "display: none;" });
        var base = window.location.href.match('(.*/)[^/]+/$')[1];
        var go = function (where) {
            window.location.assign(base+where);
        };
        for (var i=0; i < saved.length; i++) {
            menu.addChild(new dijit.MenuItem({
                label: saved[i],
                onClick: dojo.partial(go, saved[i])
            }));
        }
        return new dijit.form.ComboButton({
            label: "Saved",
            dropDown: menu
        })
    };

    dojo.xhrGet({
        url: 'load.json',
        handleAs: 'json',
        load: function (data) {
            for (var i=0; i < data.charts.length; i++) {
                params = data.charts[i];
                params.imgid = data.imgids[i];
                new Chart(params);
            }
            dojo.destroy(button_div.firstChild);
        },
        error: function (error) {alert(error)}
    });

    dojo.xhrGet({
        url: 'get_series.json',
        handleAs: 'json',
        load: function (data) {

            series = new dojo.data.ItemFileReadStore({
                data: {identifier: 'id', label: 'id',
                       items: dojo.map(data.series, function(v) {
                           return {id: v};
                       })
                      }
            });

            button_div.appendChild(new dijit.form.Button({
                label: "+",
                onClick: function () {
                    plotDialog('', [], function (title, data) {
                        new Chart(plotdata2plotparams(data, {title: title}));
                    });
                }
            }).domNode);
            button_div.appendChild(new dijit.form.Button({
                label: 'Save',
                onClick: function () { save_dialog.show(); }
            }).domNode);
            button_div.appendChild(savedMenuButton(data.saved).domNode);

        },
        error: function (error) {alert(error)}
    });
});
