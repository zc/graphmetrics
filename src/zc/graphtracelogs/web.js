dojo.require("dijit.Dialog");
dojo.require("dijit.Menu");
dojo.require("dijit.form.Button");
dojo.require("dijit.form.CheckBox");
dojo.require("dijit.form.DateTextBox");
dojo.require("dijit.form.FilteringSelect");
dojo.require("dijit.form.TextBox");
dojo.require("dijit.form.TimeTextBox");
dojo.require("dojo.data.ItemFileReadStore");
dojo.require("dojo.date.stamp");

zc = function() {
    var imgid = 0;
    var customers;

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
        })
    };

    var twodigits = function (i) {
        var result = i.toString();
        if (result.length < 2)
            result = '0' + i;
        return result;
    };

    var date2string = function (d) {
        return (d.getFullYear()
                + '-' + twodigits(d.getMonth()+1)
                + '-' + twodigits(d.getDate())
               );
    };

    var time2string = function (d) {
        return ('T'
                + d.getHours()
                + ':' + twodigits(d.getMinutes())
                + ':' + twodigits(d.getSeconds())
               );
    };
    var string2time = function (s) {
        s = s.split('T')[1].split(':');
        var result = new Date();
        result.setHours(s[0]);
        result.setMinutes(s[1]);
        result.setSeconds(s[2]);
        return result;
    };

    var newChart = function(inst, ob) {
        imgid ++;
        var div = dojo.create('div',{}, dojo.body());
        var params = {
            instance: inst,
            bust: (new Date()).toString(),
            width: div.clientWidth,
            imgid: imgid
        };
        if (ob != undefined)
            dojo.mixin(params, ob);
        var img = dojo.create(
            'img', {id: 'img'+imgid,
                    src: 'show.png?'+dojo.objectToQuery(params)}, div);
        var update_img = function (ob) {
            if (ob != undefined)
                dojo.mixin(params, ob);
            params.bust = (new Date()).toString();
            params.width = div.clientWidth;
            img.src =  'show.png?'+dojo.objectToQuery(params);
        };

        // Reload:
        dojo.connect(window, 'onresize', update_img);
        var keep_refreshing = function () {
            if (keep_refreshing == undefined)
                return;
            if (params.end == null)
                update_img();
            setTimeout(keep_refreshing, 60000);
        };
        setTimeout(keep_refreshing, 60000);
        dojo.create('br', {}, div);
        div.appendChild(new dijit.form.Button({
            label: 'Reload',
            onClick: update_img
        }).domNode);

        // Date range:
        div.appendChild(new dijit.form.DateTextBox({
            value: params.start
                ? dojo.date.stamp.fromISOString(params.start)
                : undefined,
            onChange: function(date) {
                if (date != null)
                    date = date2string(date);
                else
                    date = undefined;
                update_img({start: date});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "7em");
        dojo.place('<span>T</span>', div)
        div.appendChild(new dijit.form.TimeTextBox({
            value: params.start_time
                ? string2time(params.start_time)
                : undefined,
            onChange: function(date) {
                if (date != null)
                    date = time2string(date);
                else
                    date = undefined;
                update_img({start_time: date});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "4em");

        dojo.place('<span> to </span>', div)
        div.appendChild(new dijit.form.DateTextBox({
            value: params.end
                ? dojo.date.stamp.fromISOString(params.end)
                : undefined,
            onChange: function(date) {
                if (date != null)
                    date = date2string(date);
                update_img({end: date});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "7em");
        dojo.place('<span>T</span>', div)
        div.appendChild(new dijit.form.TimeTextBox({
            value: params.end_time
                ? string2time(params.end_time)
                : undefined,
            onChange: function(date) {
                if (date != null)
                    date = time2string(date);
                else
                    date = undefined;
                update_img({end_time: date});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "4em");

        dojo.place('<span> Trail: </span>', div)
        div.appendChild(new dijit.form.ValidationTextBox({
            value: params.trail,
            maxLength: 3,
            regExp: "[0-9]+",
            onChange: function(val) {
                update_img({trail: val});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "4em");

        dojo.place('<span> Step: </span>', div)
        div.appendChild(new dijit.form.ValidationTextBox({
            value: params.step,
            maxLength: 4,
            regExp: "[0-9]+",
            onChange: function(val) {
                update_img({step: val});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "4em");

        dojo.place('<span> Min: </span>', div)
        div.appendChild(new dijit.form.ValidationTextBox({
            value: params.lower_limit,
            maxLength: 4,
            regExp: "[0-9]+",
            onChange: function(val) {
                update_img({lower_limit: val});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "4em");

        dojo.place('<span> Max: </span>', div)
        div.appendChild(new dijit.form.ValidationTextBox({
            value: params.upper_limit,
            maxLength: 4,
            regExp: "[0-9]+",
            onChange: function(val) {
                update_img({upper_limit: val});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "4em");

        dojo.place('<span> Log: </span>', div)
        div.appendChild(new dijit.form.CheckBox({
            checked: params.log == 'y' ? 'checked' : undefined,
            onChange: function(val) {
                if (val)
                    params.log = 'y';
                else
                    params.log = 'n';
                update_img();
            }
        }).domNode);

        div.appendChild(newInstanceMenuButton(
            "Instance:",
            function(val){ update_img({instance: val}); }
        ).domNode);

        dojo.place('<span> Height: </span>', div)
        div.appendChild(new dijit.form.ValidationTextBox({
            value: params.height,
            maxLength: 4,
            regExp: "[0-9]+",
            onChange: function(val) {
                update_img({height: val});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "4em");

        div.appendChild(new dijit.form.Button({
            label: 'X',
            onClick: function () {
                keep_refreshing = undefined;
                dojo.xhrPost({
                    url: 'destroy',
                    postData: 'imgid='+params.imgid, 
                    load: function () { dojo.destroy(div); },
                    error: function (error) {alert(error)}
                });
                
            }
        }).domNode);
        dojo.style(div.lastChild, "float", "right");
    };

    var replaceAll = function(str, orig, repl) {
        while (1) {
            var news = str.replace(orig, repl)
            if (news == str) return str;
            str = news;
        }
    };

    return {
        init: function()
        {
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
            dojo.xhrGet({
                url: 'get_instances.json',
                handleAs: 'json',
                load: function (data) {
                    customers = data.customers;

                    dojo.xhrGet({
                        url: 'load.json',
                        handleAs: 'json',
                        load: function (data) {
                            for (var i=0; i < data.charts.length; i++) {
                                newChart('', data.charts[i]);
                            }
                        },
                        error: function (error) {alert(error)}
                    });

                    button_div.appendChild(
                        newInstanceMenuButton("New chart:", newChart
                                             ).domNode);
                    button_div.appendChild(new dijit.form.Button({
                        label: 'Save',
                        onClick: function () { save_dialog.show(); }
                    }).domNode);

                },
                error: function (error) {alert(error)}
            });
        }
    }
}();

dojo.addOnLoad(zc.init);
