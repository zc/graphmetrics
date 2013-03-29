dojo.require("dijit.Dialog");
dojo.require("dijit.Menu");
dojo.require("dijit.form.Button");
dojo.require("dijit.form.FilteringSelect");
dojo.require("dijit.form.TextBox");
dojo.require("dijit.Tooltip");
dojo.require("dojo.data.ItemFileReadStore");
dojo.require('zc.util');

dojo.addOnLoad(function() {
    var imgid = 0;
    var customers = [];
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
        };
        this.changed = changed;

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
        dojo.place('<span> to </span>', div);
        uis.push(new zc.util.DateTimeUI(div, params, 'end', changed));

        uis.push(new zc.util.TextUI(div, 'Trail', params, 'trail', changed,
                            5, "^[0-9]+$"));
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
        new dijit.Tooltip({
            connectId: [div.lastChild],
            label: 'Apply this scaling to all charts'
        });

        if (!customers.length) {
            this.instance_menu_container = dojo.create('span', null, div);
        }
        else {
            div.appendChild(
                newInstanceMenuButton(
                    "Instance:",
                    function(val){
                        changed({instance: val});
                    }
                ).domNode);
        }

        zc.util.TextUI(div, 'Height', params, 'height', changed, 4, "[0-9]+");

        div.appendChild(new dijit.form.Button({
            label: 'X',
            onClick: function () {
                dojo.xhrPost({
                    url: 'destroy',
                    postData: 'imgid='+params.imgid,
                    load: function () {
                        dojo.destroy(div);
                        delete charts[params['imgid']];
                    },
                    error: function (error) {alert(error); }
                });

            }
        }).domNode);
        dojo.style(div.lastChild, "float", "right");

        charts[params.imgid] = this;
    };

    var newInstanceMenuButton = function(label, instfunc) {
        var customer_menu = new dijit.Menu({ style: "display: none;" });
        for (var ic=0; ic < customers.length; ic++) {
            var hosts = customers[ic][1];
            var host_menu = new dijit.Menu({ style: "display: none;" });
            for (var ih=0; ih < hosts.length; ih++) {
                var instances = hosts[ih][1];
                var instance_menu = new dijit.Menu({ style: "display: none;" });
                for (var ii=0; ii < instances.length; ii++) {
                    instance_menu.addChild(new dijit.MenuItem({
                        label: instances[ii][0],
                        onClick: dojo.partial(instfunc, instances[ii][1])
                    }));
                }
                host_menu.addChild(new dijit.PopupMenuItem({
                    label: hosts[ih][0],
                    popup: instance_menu
                }));
            }
            customer_menu.addChild(new dijit.PopupMenuItem({
                label: customers[ic][0],
                popup: host_menu
            }));
        }
        return new dijit.form.ComboButton({
            label: label,
            dropDown: customer_menu
        });
    };

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
        });
    };

    dojo.addOnLoad(function() {

        dojo.body().appendChild(new dijit.form.Button({
           label: 'Logout',
           style: "float: right",
           onClick: function () { navigator.id.logout(); }
        }).domNode);

        var button_div = dojo.create('div',{}, dojo.body());
        dojo.create('div',
                    {innerHTML: 'Getting tracelog info ...'}, button_div);
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
                                        overwrite: 'y'
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
                    error: function (error) {alert(error); }
                });
            }
        }).domNode);
        dojo.xhrGet({
            url: 'load.json',
            handleAs: 'json',
            load: function (data) {
                for (var i=0; i < data.charts.length; i++) {
                    params = data.charts[i];
                    params.imgid = data.imgids[i];
                    new Chart(params);
                }
            },
            error: function (error) {
                alert(error);
            }
        });
        dojo.xhrGet({
            url: 'get_instances.json',
            handleAs: 'json',
            load: function (data) {
                customers = data.customers;

                dojo.destroy(button_div.firstChild);
                button_div.appendChild(
                    newInstanceMenuButton("New chart:", function (inst) {
                        new Chart({instance: inst});
                    }).domNode);
                button_div.appendChild(new dijit.form.Button({
                    label: 'Save',
                    onClick: function () { save_dialog.show(); }
                }).domNode);
                button_div.appendChild(savedMenuButton(data.saved).domNode);
                for (i in charts) {
                    (function (i) {
                        var chart = charts[i];
                        if (chart.instance_menu_container) {
                            chart.instance_menu_container.appendChild(
                                newInstanceMenuButton(
                                    "Instance:",
                                    function(val){
                                        chart.changed({instance: val});
                                    }
                                ).domNode);
                        }
                    })(i);
                }
            },
            error: function (error) {alert(error); }
        });
    });
});
