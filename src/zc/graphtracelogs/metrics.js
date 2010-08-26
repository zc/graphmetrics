dojo.require("dijit.ColorPalette");
dojo.require("dijit.Dialog");
dojo.require("dijit.form.Button");
dojo.require("dijit.form.CheckBox");
dojo.require("dijit.form.FilteringSelect");
dojo.require("dijit.form.TextBox");
dojo.require("dijit.layout.BorderContainer");
dojo.require("dijit.layout.ContentPane");
dojo.require("dijit.Menu");
dojo.require("dojo.data.ItemFileReadStore");
dojo.require("dojo.data.ItemFileWriteStore");
dojo.require("dojox.grid.cells._base");
dojo.require("dojox.grid.DataGrid");
dojo.require('zc.util');

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

    var get_query_re = function (s) {
        return new RegExp(s.split(/\s+/).join('.*'), 'i');
    };

    var MySelect = dojo.declare(dijit.form.FilteringSelect, {
        _startSearchFromInput: function(){
            this.__last_search_value = this.focusNode.value;
	    this._startSearch(this.focusNode.value);
	},
        __last_search_value: '',
        _getQueryString: get_query_re
    });

    var seriesSelectUI = function (node, callback, allcallback) {
        dojo.place(
            '<span style="font-size: large; font-weight: bold">'+
            'Start here! -&gt;</span>',
                   node);
        var select = new MySelect({
            searchAttr: 'id',
            store: series,
            queryExpr: '*${0}*',
            autoComplete: false,
            //searchDelay: 300,
            pageSize: 99,
            onChange: function (v) {
                if (v)
                    callback(v);
                select.reset();
            }
        });
        jimselect = select;
        node.appendChild(select.domNode);
        zc.util.tooltip(select.domNode,
                        'regular expression (spaces converted to .*)');
        node.appendChild(new dijit.form.Button({
            label: 'last search',
            onClick: function () {
                if (select.__last_search_value) {
                    select._abortQuery();
                    select.set('displayedValue', select.__last_search_value);
                    select._startSearch(select.__last_search_value);
                }
            }
        }).domNode);
        node.appendChild(new dijit.form.Button({
            label: 'select all',
            onClick: function () {
                if (select.__last_search_value) {
                    series.fetch({
                        query: {id: get_query_re(select.__last_search_value)},
                        onComplete: function (items) {
                            if (items.length > 99) {
                                alert('Too many '+items.length);
                                return;
                            }
                            for (var i=0; i < items.length; i++)
                                callback(series.getValue(items[i], 'id'));
                        }
                    });

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
        var aggregation_function = 'average';
        var radio_buttons = {}, custom_text;

        var pick_vname = function (store, callback, index) {
            index = index || 0;
            var vname = 'v'+index;
            store.fetch({
                query: {vname: vname},
                onComplete: function (items) {
                    if (items.length)
                        pick_vname(store, callback, index+1);
                    else
                        callback(vname);
                }
            });
            
        };

        var build_dialog = function () {
            var border = new dijit.layout.BorderContainer({
                gutters: false,
                style: 'width: 100%; height: 99%'
            });
            dialog = new dijit.Dialog({
                title:
                'Select one (or more agregated) series to define a plot data.',
                style: 'width: 640px; height: 450px',
                content: border
            });
            store = new dojo.data.ItemFileWriteStore({
                data: {
                    items: []
                }
            });
            dojo.connect(dialog, 'hide', store, 'revert');
            border.addChild(newContentPane({
                style: 'height: 5ex; width: 100%',
                region:  'top'
            }, function (node) {
                seriesSelectUI(node, function (v) {
                    pick_vname(store, function (vname) {
                        store.newItem({id: v, vname: vname});
                    });
                });
            }));
            var grid = new dojox.grid.DataGrid({
                store: store,
                style: 'width: 100%; height: 100%',
                // query: {id: '*'},
                structure: [{
                    field: 'vname',
                    name: 'Variable Name',
                    width: '100px',
                    editable: true
                }, {
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
                style: 'height: 23ex; width: 100%',
                region: 'bottom'
            }, function (node) {

                var div = dojo.place(
                    '<div style="padding: 10px; width=100%">'
                    +'Aggregation function:<br /></div>',
                    node);

                div.appendChild(
                    (radio_buttons['average'] = new dijit.form.RadioButton({
                        checked: true,
                        id: 'average-aggretaion-radio-button',
                        onClick: function () {aggregation_function='average'; },
                        name: 'function'
                    })).domNode);
                dojo.place('<label for="average-aggretaion-radio-button">'
                           +'Average       </label>', div)
                div.appendChild(
                    (radio_buttons['total'] = new dijit.form.RadioButton({
                        id: 'total-aggretaion-radio-button',
                        onClick: function () {aggregation_function='total'; },
                        name: 'function'
                    })).domNode);
                dojo.place('<label for="total-aggretaion-radio-button">'
                           +'Total</label><br />', div)
                div.appendChild(
                    (radio_buttons['custom'] = new dijit.form.RadioButton({
                        id: 'custom-aggretaion-radio-button',
                        onClick: function () {aggregation_function='custom'; },
                        name: 'function'
                    })).domNode);
                dojo.place('<label for="custom-aggretaion-radio-button">'
                           +'Custom (RRD RPN):</label></br>', div)
                custom_text = new dijit.form.ValidationTextBox({
                    style: 'width: 100%',
                });
                div.appendChild(custom_text.domNode);
                
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
                                _callback(
                                    dojo.map(items, function (item) {
                                        return store.getValue(
                                            item, 'id');
                                    }).join(',')
                                    +
                                        ',,'+aggregation_function
                                    +
                                        ','+dojo.map(items, function (item) {
                                            return store.getValue(
                                                item, 'vname');
                                        }).join(',')
                                    +
                                        ',,'+custom_text.get('value')
                                );
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

        var update_store = function (state) {
            var raw = state;
            state = state.split(',,');
            var series = state[0].split(',');
            if (state.length == 3) {
                var vnames = state[1].split(',');
                zc.util.assert(
                    vnames.length == series.length + 1,
                    "Wrong number of vnames "+raw);
                radio_buttons[vnames[0]].set('checked', true)
                aggregation_function = vnames[0]
                vnames = vnames.slice(1);
                for (var i=0; i < series.length; i++)
                    store.newItem({id: series[i], vname: vnames[i]});
                custom_text.set('value', state[2]);
                return;
            }
            for (var i=0; i < series.length; i++)
                store.newItem({id: series[i], vname: 'v'+i});

            if (state.length == 2) {
                zc.util.assert(
                    state[1] == 'total',
                    "expected total "+raw);
                aggregation_function = 'total';
                radio_buttons['total'].set('checked', true)
            }
            else
                radio_buttons['average'].set('checked', true)
        };

        // Entry point
        return function (callback, state) {
            if (dialog == undefined)
                build_dialog();
            else
                custom_text.set('value', '');

            _callback = callback;
            dialog.show();
            if (state)
                update_store(state)
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
                style: 'width: 800px; height: 400px',
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
                title_ui = new zc.util.TextUI(
                    node, 'Chart title', params, 'title',
                    function () {}, 50, '.*');
            }));

            var grid = new dojox.grid.DataGrid({
                store: store,
                style: 'width: 100%; height: 100%',
                onRowDblClick: function (e) {
                    if (e.cellIndex != 4)
                        return;
                    var item = grid.getItem(e.rowIndex);
                    seriesDialog(function (v) {
                        store.setValue(item, 'data', v);
                    }, store.getValue(item, 'data'));
                },
                structure: [
                    {
                        field: 'legend',
                        name: 'Legend',
                        width: '100px',
                        editable: 'true'
                    },
                    {
                        field: 'color',
                        name: 'Color',
                        width: '40px',
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
                            dojo.style(button.containerNode, 'height', '15px');
                            dojo.style(button.containerNode, 'width', '10px');
                            dojo.style(button.containerNode,
                                                     'backgroundColor', v);
                            return button;
                        }
                    },
                    {
                        field: 'dash',
                        name: 'Dash',
                        width: '40px',
                        type: dojox.grid.cells.Bool, editable: true
                    },
                    {
                        field: 'thick',
                        name: 'Thick',
                        width: '40px',
                        type: dojox.grid.cells.Bool, editable: true
                    },
                    {
                        field: 'data',
                        width: 'auto',
                        name: 'Series',
                        formatter: function (v) {
                            if (! v)
                                return '';
                            v = v.split(',,');
                            var data = v[0].split(',');
                            if (v.length == 1) {
                                if (data.length == 1)
                                    return data[0];
                                return data.join('<br />')+'<br/>average';
                            }

                            var vnames = v[1].split(',');
                            if (v.length > 2 && vnames[0] == 'custom') {
                                vnames = vnames.slice(1);
                                var r = '';
                                for (var i=0; i < vnames.length; i++)
                                    r += (vnames[i] + '=' + data[i] + '<br />');
                                r += 'custom rpn='+ v.slice(2).join(',,');
                                return r;
                            }
                            if (data.length == 1)
                                return data[0];
                            return data.join('<br />')+'<br/>'+vnames[0];
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
                                            data: store.getValue(item, 'data'),
                                            dash: store.getValue(item, 'dash'),
                                            thick: store.getValue(item, 'thick')
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
                                dash: !!(Math.floor(items.length /
                                                 default_colors.length
                                                   ) % 2),
                                thick: !!(Math.floor(items.length /
                                                  (default_colors.length*2)
                                                    ) % 2),
                                data: v
                            })
                        }
                    });
                }

                var select_div = dojo.create(
                    'div', {style: 'float: right'}, node);
                seriesSelectUI(select_div, newPlotItem);
                select_div.appendChild(new dijit.form.Button({
                    label: 'aggregate',
                    onClick: function () {
                        seriesDialog(newPlotItem);
                    }
                }).domNode);
                zc.util.tooltip(select_div.lastChild,
                                'aggregate multiple series');
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
                delete params['dash'+i];
                delete params['thick'+i];
            }
        } else
            params = {}

        // now update
        for (var i=0; i < data.length; i++) {
            params['legend'+i] = data[i].legend;
            params['color'+i] = data[i].color.slice(1);
            params['data'+i] = data[i].data;
            params['dash'+i] = data[i].dash ? 't' : '';
            params['thick'+i] = data[i].thick ? 't' : '';
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
                data: params['data'+i],
                dash: params['dash'+i] == 't',
                thick: params['thick'+i] == 't'
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

        uis.push(new zc.util.DateTimeUI(div, params, 'start', changed));
        dojo.place('<span> to </span>', div)
        uis.push(new zc.util.DateTimeUI(div, params, 'end', changed));

        uis.push(new zc.util.TextUI(div, 'Trail', params, 'trail', changed,
                            3, "^[0-9]+$",
                            'Trailing hours to show (ignoring time range)'));
        uis.push(new zc.util.TextUI(div, 'Step', params, 'step', changed,
                            4, "[0-9]+"));
        uis.push(new zc.util.TextUI(div, 'Min', params, 'lower_limit', changed,
                            6, "[0-9]+"));
        uis.push(new zc.util.TextUI(div, 'Max', params, 'upper_limit', changed,
                            9, "[0-9]+"));
        uis.push(new zc.util.BoolUI(div, 'Log', params, 'log', changed));

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
        zc.util.tooltip(div.lastChild, 'Apply this scaling to all charts');

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

        zc.util.TextUI(div, 'Height', params, 'height', changed, 4, "[0-9]+");

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
        zc.util.tooltip(div.lastChild, 'Remove this chart.');

        charts[params.imgid] = this;
    };

    var button_div = dojo.create('div',{}, dojo.body());
    dojo.create('div', {innerHTML: 'wait for it ...'}, button_div);
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
